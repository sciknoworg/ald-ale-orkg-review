#!/usr/bin/env python3
"""
PDF Text and Table Extractor
Extracts text and tables from PDF files using pdfplumber.
Processes folder structure: root/category/paper/*.pdf
"""

import pdfplumber
import json
import re
from typing import Dict, List, Any, Tuple
from pathlib import Path
import os


class PDFExtractor:
    """Extract text and tables from PDF files."""
    
    def __init__(self, pdf_path: str):
        """
        Initialize the PDF extractor.
        
        Args:
            pdf_path: Path to the PDF file
        """
        self.pdf_path = pdf_path
        self.pdf = None
        self.extraction_results = {
            'metadata': {},
            'pages': []
        }
        # Track accumulated text length to avoid ToC false positives
        self.accumulated_text_length = 0
        # Minimum page number to start looking for end matter (avoid ToC)
        self.min_page_for_end_matter = 3
        # Minimum accumulated text before looking for end matter
        self.min_text_length_for_end_matter = 2000
    
    def open_pdf(self):
        """Open the PDF file."""
        self.pdf = pdfplumber.open(self.pdf_path)
        self.extraction_results['metadata'] = self.pdf.metadata or {}
        
    def close_pdf(self):
        """Close the PDF file."""
        if self.pdf:
            self.pdf.close()
    
    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text by removing excessive whitespace while preserving structure.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        
        # Replace multiple newlines with maximum of 2 (preserve paragraph breaks)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove spaces at the beginning and end of lines
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        # Remove trailing whitespace
        text = text.strip()
        
        return text
    
    def _should_check_for_end_matter(self, page_num: int) -> bool:
        """
        Determine if we should check for end matter on this page.
        Avoids false positives from table of contents in early pages.
        
        Args:
            page_num: Current page number (0-indexed)
            
        Returns:
            True if we should check for end matter, False otherwise
        """
        # Don't check first few pages (likely to contain ToC)
        if page_num < self.min_page_for_end_matter:
            return False
        
        # Don't check if we haven't accumulated enough text yet
        if self.accumulated_text_length < self.min_text_length_for_end_matter:
            return False
        
        return True
    
    def _find_end_matter_start(self, text: str) -> int:
        """
        Find the start position of end matter sections.
        
        Args:
            text: Text to search
            
        Returns:
            Position of end matter start, or -1 if not found
        """
        # Patterns for end matter sections
        # Using word boundaries to avoid partial matches
        patterns = [
            # References patterns (title-case or all caps, at start of line)
            r'^\s*(?-i:References)\b',
            r'^\s*(?-i:REFERENCES)\b',

            # Bibliography patterns
            r'^\s*Bibliograph(?:y|ies)\b',
            r'^\s*BIBLIOGRAPHY\b',
            r'^\s*Works Cited\b',

            # Funding patterns
            r'^\s*Funding sources?\b',
            r'^\s*Funding Sources?\b',
            r'^\s*FUNDING\b',
            r'^\s*Financial support\b',
            r'^\s*Financial Support\b',

            # Conflicts patterns
            r'^\s*Conflicts? of [Ii]nterest\b',
            r'^\s*Competing [Ii]nterests?\b',
            r'^\s*COMPETING INTERESTS?\b',

            # Acknowledgments / Acknowledgements (US + UK)
            r'^\s*Acknowledg(?:e)?ments?\b',
            r'^\s*ACKNOWLEDG(?:E)?MENTS?\b',

            # Appendix patterns
            r'^\s*Appendix(?:\s+[A-Z0-9]+)?\b',
            r'^\s*APPENDIX(?:\s+[A-Z0-9]+)?\b',
            r'^\s*Appendices\b',
            r'^\s*APPENDICES\b',
        ]

        earliest_pos = -1

        # NEW: find "Abstract" heading on this page, if any
        abstract_match = re.search(r'^\s*Abstract\b', text,
                                   re.IGNORECASE | re.MULTILINE)
        abstract_pos = abstract_match.start() if abstract_match else -1

        for pattern in patterns:
            # Look for potential end-matter headers
            for match in re.finditer(pattern, text,
                                     re.IGNORECASE | re.MULTILINE):
                pos = match.start()

                # NEW: if this match is *above* the Abstract heading on this page,
                # treat it as part of the Contents / ToC and ignore it
                if abstract_pos != -1 and pos < abstract_pos:
                    continue

                # Existing validation: check if it looks like a section header
                # (standalone line, possibly with preceding newline)
                start_check = max(0, pos - 2)
                context_before = text[start_check:pos]

                # Should either be at start of text, or have a newline just before it,
                # or be preceded only by whitespace in the last 2 characters
                if (
                    pos == 0 or
                    '\n' in context_before or
                    context_before.strip() == ''
                ):
                    if earliest_pos == -1 or pos < earliest_pos:
                        earliest_pos = pos

        return earliest_pos
    
    def extract_text_from_page(self, page, layout=False) -> str:
        """
        Extract and clean text from a single page.
        
        Args:
            page: pdfplumber.Page object
            layout: If True, preserve layout. If False, extract as continuous text
            
        Returns:
            Extracted and cleaned text as string
        """
        # Use layout=False for cleaner text without excessive whitespace
        text = page.extract_text(layout=layout)
        text = text if text else ""
        
        # Clean the text
        text = self._clean_text(text)
        
        return text
    
    def _is_table_complex(self, table: List[List[str]]) -> bool:
        """
        Determine if a table is complex (irregular structure).
        Simple tables have consistent number of columns per row.
        
        Args:
            table: Table data as list of rows
            
        Returns:
            True if table is complex, False if simple
        """
        if not table or len(table) < 2:
            return True
        
        # Check if all rows have the same number of columns
        column_counts = [len(row) for row in table if row]
        
        if not column_counts:
            return True
        
        # If all rows have same column count, it's simple
        if len(set(column_counts)) == 1:
            return False
        
        # If column counts vary significantly, it's complex
        return True
    
    def _table_to_text(self, table: List[List[str]]) -> str:
        """
        Convert a table to text format (for complex tables).
        
        Args:
            table: Table data as list of rows
            
        Returns:
            Text representation of table
        """
        lines = []
        for row in table:
            if row:
                # Join cells with pipes, filter out None values
                cells = [str(cell) if cell is not None else '' for cell in row]
                lines.append(' | '.join(cells))
        
        return '\n'.join(lines)
    
    def extract_tables_from_page(self, page) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Extract all tables from a single page.
        Classifies tables as simple (structured data) or complex (text).
        
        Args:
            page: pdfplumber.Page object
            
        Returns:
            Tuple of (simple_tables, complex_tables_as_text)
            - simple_tables: List of dicts with structured table data
            - complex_tables_as_text: List of text representations
        """
        tables = page.extract_tables()
        
        if not tables:
            return [], []
        
        simple_tables = []
        complex_tables = []
        
        for table_idx, table in enumerate(tables):
            if self._is_table_complex(table):
                # Complex table - convert to text
                table_text = self._table_to_text(table)
                complex_tables.append({
                    'table_index': table_idx + 1,
                    'type': 'complex',
                    'text': table_text
                })
            else:
                # Simple table - keep as structured data
                simple_tables.append({
                    'table_index': table_idx + 1,
                    'type': 'simple',
                    'data': table
                })
        
        return simple_tables, complex_tables
    
    def extract_page(self, page_num: int) -> Dict[str, Any]:
        """
        Extract text and tables from a single page.
        
        Args:
            page_num: Page number (0-indexed)
            
        Returns:
            Dictionary containing page data
        """
        page = self.pdf.pages[page_num]
        
        text = self.extract_text_from_page(page)
        simple_tables, complex_tables = self.extract_tables_from_page(page)
        
        page_data = {
            'page_number': page_num + 1,  # 1-indexed for human readability
            'text': text,
            'simple_tables': simple_tables,
            'complex_tables': complex_tables,
            'dimensions': {
                'width': page.width,
                'height': page.height
            }
        }
        
        return page_data
    
    def extract_all(self, exclude_end_matter: bool = True) -> Dict[str, Any]:
        """
        Extract text and tables from all pages in the PDF.
        
        Args:
            exclude_end_matter: If True, stop extraction at end matter sections
                              (References, Funding, Acknowledgements, Conflicts of interest, Appendix)
                              Will NOT stop if these appear in a ToC at the beginning.
        
        Returns:
            Dictionary containing all extraction results
        """
        self.open_pdf()
        
        try:
            total_pages = len(self.pdf.pages)
            print(f"Processing {total_pages} pages...")
            
            end_matter_found = False
            self.accumulated_text_length = 0
            
            for page_num in range(total_pages):
                if end_matter_found and exclude_end_matter:
                    break
                    
                print(f"  Extracting page {page_num + 1}/{total_pages}...")
                page_data = self.extract_page(page_num)
                
                # Update accumulated text length
                self.accumulated_text_length += len(page_data['text'])
                
                # Check if this page contains the start of end matter
                # Only check after minimum page number and accumulated text to avoid ToC
                if exclude_end_matter and not end_matter_found:
                    if self._should_check_for_end_matter(page_num):
                        end_pos = self._find_end_matter_start(page_data['text'])
                        if end_pos != -1:
                            # Truncate text at end matter section
                            page_data['text'] = page_data['text'][:end_pos].rstrip()
                            # Clear tables after end matter
                            page_data['simple_tables'] = []
                            page_data['complex_tables'] = []
                            end_matter_found = True
                            print(f"  End matter section found on page {page_num + 1}, stopping extraction...")
                
                self.extraction_results['pages'].append(page_data)
            
            print("Extraction complete!")
            return self.extraction_results
            
        finally:
            self.close_pdf()
    
    def save_results_json(self, output_path: str):
        """
        Save extraction results to a JSON file.
        
        Args:
            output_path: Path to save the JSON file
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.extraction_results, f, indent=2, ensure_ascii=False)
        print(f"      Saved to {Path(output_path).name}")
    
    def get_formatted_output(self) -> str:
        """
        Get a formatted text representation of the extraction results.
        Useful for feeding to an LLM.
        
        Returns:
            Formatted string containing all extracted content
        """
        output_lines = []
        
        # Add metadata
        output_lines.append("=" * 80)
        output_lines.append("PDF METADATA")
        output_lines.append("=" * 80)
        for key, value in self.extraction_results['metadata'].items():
            output_lines.append(f"{key}: {value}")
        output_lines.append("")
        
        # Add page contents
        for page in self.extraction_results['pages']:
            output_lines.append("=" * 80)
            output_lines.append(f"PAGE {page['page_number']}")
            output_lines.append("=" * 80)
            output_lines.append("")
            
            # Add text
            output_lines.append("--- TEXT CONTENT ---")
            output_lines.append(page['text'])
            output_lines.append("")
            
            # Add simple tables
            if page['simple_tables']:
                output_lines.append("--- SIMPLE TABLES (Structured Data) ---")
                for table_data in page['simple_tables']:
                    output_lines.append(f"\nTable {table_data['table_index']} (Simple):")
                    for row in table_data['data']:
                        output_lines.append(str(row))
                output_lines.append("")
            
            # Add complex tables
            if page['complex_tables']:
                output_lines.append("--- COMPLEX TABLES (Text Format) ---")
                for table_data in page['complex_tables']:
                    output_lines.append(f"\nTable {table_data['table_index']} (Complex):")
                    output_lines.append(table_data['text'])
                output_lines.append("")
            
            if not page['simple_tables'] and not page['complex_tables']:
                output_lines.append("--- NO TABLES FOUND ---")
                output_lines.append("")
        
        return "\n".join(output_lines)


def process_folder_structure(root_path: str, exclude_end_matter: bool = True) -> Dict[str, Any]:
    """
    Process entire folder structure: root/category/paper/*.pdf
    Extracts content and saves JSON files in the same directory as each PDF.
    
    Args:
        root_path: Path to root directory
        exclude_end_matter: If True, exclude end matter sections (References, etc.)
        
    Returns:
        Dictionary containing all extraction results organized by category and paper
    """
    root = Path(root_path)
    
    if not root.exists():
        print(f"Error: Root path '{root_path}' does not exist!")
        return None
    
    if not root.is_dir():
        print(f"Error: Root path '{root_path}' is not a directory!")
        return None
    
    all_results = {
        'root_path': str(root),
        'categories': {}
    }
    
    # Iterate through category folders (e.g., ALD, ALE)
    category_folders = [d for d in root.iterdir() if d.is_dir()]
    
    if not category_folders:
        print(f"Warning: No category folders found in {root_path}")
        return all_results
    
    print(f"\nFound {len(category_folders)} category folders")
    
    for category_folder in sorted(category_folders):
        category_name = category_folder.name
        print(f"\n{'='*80}")
        print(f"Processing category: {category_name}")
        print(f"{'='*80}")
        
        all_results['categories'][category_name] = {
            'papers': {}
        }
        
        # Iterate through paper folders (e.g., paper1, paper2)
        paper_folders = [d for d in category_folder.iterdir() if d.is_dir()]
        
        print(f"  Found {len(paper_folders)} paper folders in {category_name}")
        
        for paper_folder in sorted(paper_folders):
            paper_name = paper_folder.name
            print(f"\n  Processing paper: {category_name}/{paper_name}")
            
            # Find all PDF files in this paper folder
            pdf_files = list(paper_folder.glob("*.pdf"))
            
            if not pdf_files:
                print(f"    No PDF files found in {paper_folder}")
                continue
            
            print(f"    Found {len(pdf_files)} PDF file(s)")
            
            all_results['categories'][category_name]['papers'][paper_name] = {
                'pdf_files': {}
            }
            
            # Process each PDF file
            for pdf_file in sorted(pdf_files):
                print(f"      Processing: {pdf_file.name}")
                
                try:
                    extractor = PDFExtractor(str(pdf_file))
                    results = extractor.extract_all(exclude_end_matter=exclude_end_matter)
                    
                    # Store results
                    all_results['categories'][category_name]['papers'][paper_name]['pdf_files'][pdf_file.name] = results
                    
                    # Save individual JSON file in the same directory as the PDF
                    json_filename = f"{pdf_file.stem}_extracted.json"
                    json_path = paper_folder / json_filename
                    extractor.save_results_json(str(json_path))
                    
                    print(f"      ✓ Successfully processed {pdf_file.name}")
                    
                except Exception as e:
                    print(f"      ✗ Error processing {pdf_file.name}: {str(e)}")
                    all_results['categories'][category_name]['papers'][paper_name]['pdf_files'][pdf_file.name] = {
                        'error': str(e)
                    }
    
    return all_results


# Convenience function for importing in other workflows
def extract_from_folder(root_path: str, verbose: bool = False, exclude_end_matter: bool = True) -> Dict[str, Any]:
    """
    Extract text and tables (excluding end matter) from all PDFs in the folder structure.
    This function is designed to be imported and used in other workflows.
    
    Args:
        root_path: Path to root directory containing category folders
        verbose: If True, print progress messages
        exclude_end_matter: If True, exclude end matter sections
        
    Returns:
        Dictionary containing all extraction results organized by category and paper
        
    Example:
        >>> from pdf_extractor import extract_from_folder
        >>> results = extract_from_folder('/path/to/root')
        >>> # Access data: results['categories']['ALD']['papers']['paper1']['pdf_files']['doc.pdf']
    """
    # Temporarily redirect output if not verbose
    import sys
    from io import StringIO
    
    if not verbose:
        old_stdout = sys.stdout
        sys.stdout = StringIO()
    
    try:
        results = process_folder_structure(root_path, exclude_end_matter=exclude_end_matter)
        return results
    finally:
        if not verbose:
            sys.stdout = old_stdout


def get_summary(results: Dict[str, Any]) -> str:
    """
    Generate a summary of the extraction results.
    
    Args:
        results: Dictionary containing all extraction results
        
    Returns:
        Summary string
    """
    summary_lines = []
    summary_lines.append("\n" + "="*80)
    summary_lines.append("EXTRACTION SUMMARY")
    summary_lines.append("="*80)
    
    total_categories = len(results.get('categories', {}))
    total_papers = 0
    total_pdfs = 0
    total_pages = 0
    
    for category_name, category_data in results.get('categories', {}).items():
        papers_in_category = len(category_data.get('papers', {}))
        total_papers += papers_in_category
        
        for paper_name, paper_data in category_data.get('papers', {}).items():
            pdfs_in_paper = len(paper_data.get('pdf_files', {}))
            total_pdfs += pdfs_in_paper
            
            for pdf_name, pdf_data in paper_data.get('pdf_files', {}).items():
                if 'pages' in pdf_data:
                    total_pages += len(pdf_data['pages'])
    
    summary_lines.append(f"Root path: {results.get('root_path', 'N/A')}")
    summary_lines.append(f"Total categories: {total_categories}")
    summary_lines.append(f"Total papers: {total_papers}")
    summary_lines.append(f"Total PDF files processed: {total_pdfs}")
    summary_lines.append(f"Total pages extracted: {total_pages}")
    summary_lines.append("")
    
    # Detailed breakdown by category
    for category_name, category_data in results.get('categories', {}).items():
        summary_lines.append(f"\nCategory: {category_name}")
        for paper_name, paper_data in category_data.get('papers', {}).items():
            pdfs_count = len(paper_data.get('pdf_files', {}))
            summary_lines.append(f"  {paper_name}: {pdfs_count} PDF(s)")
    
    summary_lines.append("="*80)
    
    return "\n".join(summary_lines)


def main():
    """Main function to demonstrate usage."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python pdf_extractor.py <root_folder>")
        print("\nFolder structure expected:")
        print("  root/")
        print("    ├── ALD/")
        print("    │   ├── paper1/")
        print("    │   │   └── *.pdf")
        print("    │   └── paper2/")
        print("    │       └── *.pdf")
        print("    └── ALE/")
        print("        └── paperx/")
        print("            └── *.pdf")
        print("\nExample:")
        print("  python pdf_extractor.py /path/to/root")
        print("\nFeatures:")
        print("  ✓ Clean text extraction (no excessive whitespace)")
        print("  ✓ End matter exclusion (References, Funding, Conflicts, Acknowledgements, Appendix)")
        print("  ✓ Table of Contents aware (won't stop at ToC entries)")
        print("  ✓ Simple tables as structured data, complex tables as text")
        print("  ✓ JSON files saved alongside each PDF")
        sys.exit(1)
    
    root_path = sys.argv[1]
    
    # Process all PDFs in folder structure
    print(f"\nStarting PDF extraction from: {root_path}")
    print("Note: End matter sections will be excluded from extraction")
    print("Note: Table of Contents entries will not trigger early stopping\n")
    
    results = process_folder_structure(root_path, exclude_end_matter=True)
    
    if results:
        # Print summary
        print(get_summary(results))
        print("\n✓ All PDFs processed successfully!")
        print("✓ JSON files saved in each paper's directory")
    else:
        print("\n✗ Processing failed!")


if __name__ == "__main__":
    main()
# ALD & ALE ORKG Machine-Actionable Tables: Papers and Exact NL Queries

Below are the **exact natural-language queries (NL)** and corresponding **SPARQL TinyURL links** used for machine-actionable ORKG comparisons generated from the ALD and ALE review papers.

---

# Table of Contents

## ALD
- [Paper 1](#paper-1)  
  - [Table 2](#table-2-r1469158)  
- [Paper 2](#paper-2)  
  - [Table 3](#table-3-r1469383)  
  - [Table 4](#table-4-r1469594)  
- [Paper 3](#paper-3)  
  - [Table 2](#table-2-r1469955)  
  - [Table 3](#table-3-r1471077)  
  - [Table 4](#table-4-r1470110)  
  - [Table 5](#table-5-r1469991)  
  - [Cross-table queries](#cross-table-queries-paper-3)

## ALE
- [Paper 1](#paper-1-1)  
  - [Table I](#table-i-r1562672)
- [Paper 2](#paper-2-1)  
  - [Table III](#table-iii-r1563034)
- [Paper 3](#paper-3-1)  
  - [Table 3](#table-3-r1560222)
- [Paper 4](#paper-4)  
  - [Table 1](#table-1-r1560825)
- [Paper 5](#paper-5)  
  - [Table 2](#table-2-r1563131)
- [Paper 6](#paper-6)  
  - [Cross-table I & II](#11-cross-table-nl-easy-query)  
  - [Cross-table III & IV](#12-cross-table-nl-easy-query)  
  - [Cross-table I/II/III](#13-cross-table-nl-complex-query)  
  - [Cross-table V/VI](#14-cross-table-nl-complex-query)

---

# ALD

## Paper 1
**Saturation profile based conformality analysis for atomic layer deposition: aluminum oxide in lateral high-aspect-ratio channels**  
https://doi.org/10.1039/D0CP03358H

### Table 2 (R1469158)
https://orkg.org/comparisons/R1469158

#### 1. NL easy query  
`Short`: Show all combinations of reactor types and LHAR structures reported in the ORKG comparison, and count how many times each combination occurs across the included studies.  
`Detailed`: Please extract all combinations of reactor types and LHAR structures from Table 2 of the article titled "Saturation profile based conformality analysis for atomic layer deposition: aluminum oxide in lateral high-aspect-ratio channels". Count how many times each combination occurs across the included studies. The result must be returned as one single table only, in CSV format, with one row per result. The table should have the following columns: reactor_value, lhar_value, n.  
`SPARQL`: https://tinyurl.com/lhr-reactor

#### 2. NL complex query  
`Short`: At 300 °C in PillarHall-3, what were the cTMA values reported across studies (ORKG comparison resource R1469158)? 
`Detailed`: Please extract all rows from Table 2 where the temperature is 300 °C and the LHAR type contains "pillarhall-3". For each matching row, include the contribution, paper, paper title, temperature, LHAR type, and cTMA values. The result must be returned as one single table only, in CSV format, with one row per result, and with the following columns: temp, lharText, cTMA.  
`SPARQL`: https://tinyurl.com/pillarhall3-ctma

---

## Paper 2
**Atomic layer deposition on particulate materials from 1988 through 2023: A quantitative review of technologies, materials and applications**  
https://doi.org/10.48550/arXiv.2506.17725

### Table 3 (R1469383)
https://orkg.org/comparisons/R1469383

#### 3. NL easy query  
`Short`:  Which phosphors were coated with SiO₂ in the ORKG comparison R1469383 that represents Table 3 of the review ‘Atomic layer deposition on particulate materials from 1988 through 2023: A quantitative review of technologies, materials and applications’? 
`Detailed`: Please provide a table in CSV format that includes all rows from Table 3 of the paper "Atomic layer deposition on particulate materials from 1988 through 2023: A quantitative review of technologies, materials and applications" where the coating material contains "SiO2". The table should have columns for "phosphor", and "coating", with one row per result.  
`SPARQL`: https://tinyurl.com/Phosphor-SiO2-ALD  

#### 4. NL complex query  
`Short`:  Among Eu²⁺-doped phosphors with red emission in the ORKG comparison R1469383 (Table 3 of ‘Atomic layer deposition on particulate materials from 1988 through 2023: A quantitative review of technologies, materials and applications’), which ALD coatings were deposited at temperatures ≤150 °C with optimal thickness ≤20 nm, and what precursor schemes were used?  
`Detailed`: In Table 3 of the paper titled "Atomic layer deposition on particulate materials from 1988 through 2023: A quantitative review of technologies, materials and applications," retrieve all rows where the phosphor material contains "Eu2+" and the emission color is "red." Additionally, filter the rows to include only those where the ALD deposition temperature is less than or equal to 150 °C and the ALD coating thickness is less than or equal to 20 nm. For each qualifying row, include the phosphor material, coating material, ALD precursor scheme, ALD deposition temperature, and ALD coating thickness. The result must be returned as one single table only, in CSV format, with one row per result, and with the following columns: phosphor_value, coating_value, precursors_value, temp_num, thick_num.  
`SPARQL`: https://tinyurl.com/Red-Eu2-ALD-thinlowT  

---

### Table 4 (R1469594)
https://orkg.org/comparisons/R1469594

#### 5. NL easy query  
Short: Which support materials were coated at ≤ 40 °C in the ORKG comparison R1469594 (Table 4 of ‘Atomic layer deposition on particulate materials from 1988 through 2023: A quantitative review of technologies, materials and applications’), and which precursor pairs were used, along with the reported coating thickness?  
Detailed: Please extract all rows from Table 4 of the article titled "Atomic layer deposition on particulate materials from 1988 through 2023: A quantitative review of technologies, materials and applications" where the deposition temperature is 40 °C or lower. For each row, include the support material, the precursors used, the deposition temperature, and the reported coating thickness. The result must be returned as one single table only, in CSV format, with one row per result. The table should have the following columns: support_value, precursors_value, temp_num, thickness_text.  
SPARQL: https://tinyurl.com/less-than-40  

#### 6. NL complex query  
Short: Among low-temperature runs (< 70 °C) that produced thin coatings (< 20 nm) in the ORKG comparison R1469594 (Table 4 of ‘Atomic layer deposition on particulate materials from 1988 through 2023: A quantitative review of technologies, materials and applications’), list the support material, precursor pair, deposition temperature, coating thickness, and—when alumina is implied by TMA-based precursors—classify the Al₂O₃ growth-per-cycle (GPC) as slow (< 0.4 nm), average (0.4–1.0 nm), or fast (> 1.0 nm).  
Detailed: In Table 4 of the article "Atomic layer deposition on particulate materials from 1988 through 2023: A quantitative review of technologies, materials and applications," identify the rows where the deposition temperature is less than 70 °C and the coating thickness is less than 20 nm. For each of these rows, extract the support material, ALD precursors, deposition temperature, coating thickness, and growth per cycle (GPC). If the ALD precursors include "TMA/", classify the GPC as 'slow' if it is less than 0.4 nm, 'average' if it is between 0.4 nm and 1.0 nm, and 'fast' if it is greater than 1.0 nm. If the GPC is not available or the precursors do not include "TMA/", label the GPC classification as 'n/a'. Return the results as one single table only, in CSV format, with one row per result, and with the following columns: support_value, precursors_value, temp_num, thick_num, gpc_num_nm, gpc_class.  
SPARQL: https://tinyurl.com/pharma-hard-query

---

## Paper 3
**Atomic and Molecular Layer Deposition of Functional Thin Films Based on Rare Earth Elements**  
https://doi.org/10.1002/admi.202400274

### Table 2 (R1469955)
https://orkg.org/comparisons/R1469955

#### 7. NL easy query  
Short: For each application (e.g. luminescence, memory, gate dielectrics, electrolytes), which rare-earth dopants appear on the largest number of distinct host materials in the ORKG comparison R1469955 (Table 2 of ‘Atomic and Molecular Layer Deposition of Functional Thin Films Based on Rare Earth Elements’)? Count the number of unique hosts per dopant and application to identify the most versatile dopants within each functional category.  
Detailed: For each application (e.g., luminescence, memory, gate dielectrics, electrolytes) listed in Table 2 of the paper titled "Atomic and Molecular Layer Deposition of Functional Thin Films Based on Rare Earth Elements," identify the rare-earth dopants that appear on the largest number of distinct host materials. Count the number of unique host materials per dopant and application to determine the most versatile dopants within each functional category. The result must be returned as one single table only, in CSV format, with one row per result, and with the following columns: application, dopant, n_hosts.  
SPARQL: https://tinyurl.com/versatile-dopants  

#### 8. NL complex query  
Short: Which host materials appear in two or more different application domains in the ORKG comparison R1469955 (Table 2 of ‘Atomic and Molecular Layer Deposition of Functional Thin Films Based on Rare Earth Elements’)? For each such ‘cross-functional’ host, list the number of distinct applications, and enumerate all (application, dopant) combinations under which the host is used.  
Detailed: Please identify the host materials from Table 2 of the article "Atomic and Molecular Layer Deposition of Functional Thin Films Based on Rare Earth Elements" that appear in two or more different application domains. For each of these 'cross-functional' host materials, list the number of distinct applications and enumerate all combinations of applications and dopants under which the host is used. The result must be returned as one single table only, in CSV format, with one row per result, and with the following columns: host, n_apps, application, dopant.  
SPARQL: https://tinyurl.com/cross-functional-hosts  

---

### Table 3 (R1471077)
https://orkg.org/comparisons/R1471077

#### 9. NL easy query  
Short: List all rare-earth ALD processes that achieve high growth per cycle (GPC ≥ 1 Å) at low deposition temperature (≤ 250 °C). Report the deposited material, the metal precursor family (e.g. Cp-derived, amidinate, β-diketonate), the co-reactant, the GPC value, and the deposition temperature, and sort the results by GPC.  
Detailed: Please extract all rows from Table 3 of the article "Atomic and Molecular Layer Deposition of Functional Thin Films Based on Rare Earth Elements" where the growth per cycle (GPC) is greater than or equal to 1 Å and the deposition temperature is less than or equal to 250 °C. For each qualifying row, include the deposited material, the family of the metal precursor (categorized as Cp-derived, amidinate, formamidinate, guanidinate, β-diketonate, alkoxide/amide, or other), the co-reactant, the GPC value, and the deposition temperature. The result must be returned as one single table only, in CSV format, with one row per result, and with the following columns: material, family, co_reactant, gpc_num, temp_num.  
SPARQL: https://tinyurl.com/ald-highgpc-lowtemp  

#### 10. NL hard query  
Short: For Y₂O₃ only, compare average growth per cycle (GPC) between plasma-enhanced ALD (PE-ALD) and thermal ALD within the 200–300 °C temperature window. For each mode (PE vs. thermal), return the ALD mode, the average GPC (in Å/cycle), the number of contributing table rows, and an example co-reactant description.  
Detailed: For Table 3 in the article titled "Atomic and Molecular Layer Deposition of Functional Thin Films Based on Rare Earth Elements," retrieve rows where the material is Y₂O₃ (or its equivalents like yttria or yttrium oxide) and the deposition temperature overlaps with the range of 200–300 °C. For each row, determine the ALD mode as either "PE-ALD" if any co-reactant contains the term "plasma," or "Thermal ALD" otherwise. Calculate the average growth per cycle (GPC) in Å/cycle for each mode, the number of contributing rows, and provide an example co-reactant description.
The result must be returned as one single table only, in CSV format, with one row per result. The table should have the following columns: mode, avg_gpc_A, n_rows, example_co_reactant.  
SPARQL: https://tinyurl.com/ald-y2o3-gpc200  

---

### Table 4 (R1470110)
https://orkg.org/comparisons/R1470110

#### 11. NL easy query  
Short: List all rare-earth ALD/MLD hybrid films that achieve high growth per cycle (GPC ≥ 5 Å) at low deposition temperature (≤ 250 °C). For each entry, report the material system, the metal precursor family (e.g. R(thd)₃, R(dpdmg)₃), the organic precursor, the GPC, and the deposition temperature, and sort the results by GPC.  
Detailed: Please extract all rows from Table 4 where the growth per cycle (GPC) is greater than or equal to 5 Å and the deposition temperature is less than or equal to 250 °C. For each row, include the material system, metal precursor, organic precursor, metal precursor family, GPC, and deposition temperature. Classify the metal precursor family based on the presence of specific ligand tags: '(dpdmg)' as 'R(dpdmg)3', '(thd)' as 'R(thd)3', '(amd)' as 'R(amd)3', '(famd)' as 'R(famd)3', '(guan)' as 'R(guan)3', and any other as 'other'. The result must be returned as one single table only, in CSV format, with one row per result, and with the following columns: material_system, metal_precursor, organic_precursor, family, gpc_num, temp_num.  
SPARQL: https://tinyurl.com/HiGLoT-query  

#### 12. NL complex query  
Short: Group rare-earth ALD/MLD hybrid films by organic linker family (terephthalate, pyridinedicarboxylate, naphthalenedicarboxylate, pyrazine-based, other) and compute the average growth per cycle (GPC) for each family, considering only films deposited at temperatures ≤ 250 °C.  
Report, for each linker family, the average GPC and the number of films contributing to this average, and sort the families by descending average GPC.  
Detailed: Please analyze Table 4 from the paper titled "Atomic and Molecular Layer Deposition of Functional Thin Films Based on Rare Earth Elements" (DOI: 10.1002/admi.202400274). Group the rare-earth ALD/MLD hybrid films by organic linker family (terephthalate, pyridinedicarboxylate, naphthalenedicarboxylate, pyrazine-based, other) and compute the average growth per cycle (GPC) for each family, considering only films deposited at temperatures ≤ 250 °C.  
For each linker family, report the average GPC and the number of films contributing to this average. Sort the families by descending average GPC.  
The result must be returned as one single table only, in CSV format, with one row per result. The table should have the following columns: linker_family, avg_gpc, n_films.  
SPARQL: https://tinyurl.com/aldmld-linker-gpc

---

### Table 5 (R1469991)
https://orkg.org/comparisons/R1469991

#### 13. NL easy query  
Short: Among Er³⁺ MOSLEDs in the comparison, which host matrices achieved high external quantum efficiency (EQE ≥ 10%) at the lowest threshold voltage, and what annealing temperatures and lifetimes (emission lifetime τ and operational device lifetime OLT) were reported?  
Return, for each qualifying host matrix, the EQE, threshold voltage, annealing temperature, τ, and OLT, and sort the results by increasing threshold voltage and, within the same voltage, by decreasing EQE.  
Detailed: Among Er³⁺ MOSLEDs in Table 5, identify the host matrices that achieved a high external quantum efficiency (EQE ≥ 10%) and report their threshold voltage, annealing temperature, emission lifetime (τ), and operational device lifetime (OLT). For each qualifying host matrix, provide the EQE, threshold voltage, annealing temperature, τ, and OLT. Sort the results by increasing threshold voltage and, within the same voltage, by decreasing EQE. Ensure the result is returned as one single table only, in CSV format, with one row per result, and with the following column headers: host_matrix, eqe_num, vol_num, anneal_num, tau_num, olt_num.  
SPARQL: https://tinyurl.com/mosled-high-eqe  

#### 14. NL complex query  
Short: Compute an efficiency-per-volt metric, defined as external quantum efficiency divided by threshold voltage (EQE/Vol), for all Er³⁺ MOSLED entries in the comparison.  
Return, for each host matrix, the EQE, threshold voltage, the derived EQE-per-Volt value, and (optionally) the annealing temperature, emission lifetime (τ), and operational device lifetime (OLT).  
Rank the host matrices by descending EQE-per-Volt, breaking ties by lower threshold voltage and then higher EQE, to highlight materials that deliver high emission efficiency at low operating voltage.  
Detailed: Please extract data from Table 5 of the article titled "Atomic and Molecular Layer Deposition of Functional Thin Films Based on Rare Earth Elements" with DOI 10.1002/admi.202400274.

For each row in Table 5, retrieve the following columns:
- Host matrix
- External quantum efficiency (EQE)
- Threshold voltage (Vol)
- Annealing temperature (Ann. T)
- Emission lifetime (τ)
- Operational device lifetime (OLT)

Calculate the efficiency-per-volt metric as the external quantum efficiency divided by the threshold voltage (EQE/Vol). Ensure that both EQE and Vol are numeric and that Vol is greater than 0.

Return the results as one single table only, in CSV format, with one row per result. The table should have the following columns:
- host_matrix
- eqe_num
- vol_num
- eqe_per_vol
- anneal_num
- tau_num
- olt_num

Order the results by descending efficiency-per-volt, then by ascending threshold voltage, and finally by descending external quantum efficiency and host matrix name.  
SPARQL: https://tinyurl.com/mosled-pareto-score

---

### Cross-table queries (Paper 3)

#### 15. Tables 3 and 5 (easy query) 
Short: Show the ALD recipe alongside device performance for Er³⁺-based MOSLED host matrices. Join MOSLED performance (Table 5) with ALD process entries (Table 3) and report host, best EQE, ALD material, metal precursor, co-reactant, precursor family, GPC, and deposition temperature. Sort by decreasing EQE.  
Detailed: Retrieve the ALD recipe alongside device performance for Er³⁺-based MOSLED host matrices from the article titled "Atomic and Molecular Layer Deposition of Functional Thin Films Based on Rare Earth Elements" with DOI 10.1002/admi.202400274.

For every host matrix reported in Table 5, retrieve the highest external quantum efficiency (EQE) observed for that host. Join these hosts to the corresponding ALD process entries in Table 3, and for each matched host–process pair, report the following:

- The host matrix,
- The best EQE value for that matrix,
- The ALD process material,
- The metal precursor,
- Any listed co-reactant,
- The inferred metal-precursor family (based on ligand chemistry),
- The growth per cycle (GPC), and
- The deposition temperature.

Sort the results by decreasing EQE to highlight ALD process recipes associated with the most efficient Er³⁺ MOSLED hosts.

The result must be returned as exactly one table only, in CSV format, with one row per result, and with the following column headers: matrix, eqe_best, process_material, metal_precursor, co_reactant_any, family, gpc_num, temp_num.  
SPARQL: https://tinyurl.com/t3t5-lowT

#### 16. Tables 2 and 5 (easy query) 
Short: Which luminescent materials listed as doped systems in the ALD dopant overview (Table 2) also have MOSLED performance data?  
Detailed: Which luminescent materials listed as doped systems in the ALD dopant overview (Table 2) also have measured MOSLED performance reported in the rare-earth MOSLED performance comparison (Table 5)? For each overlapping host material, return the performance parameters (EQE, threshold voltage, power efficiency, annealing temperature, emission lifetime τ, and operational lifetime OLT) reported in the MOSLED comparison. The result must be returned as exactly one table only, in CSV format, with one row per result. The table should have the following columns: "ml" (material label), "ppL" (performance predicate label), and "perf_val" (performance value).  
SPARQL: https://tinyurl.com/LumMOSLED-query

#### 17. Tables 3 and 5 (complex query 1)  
Short: For each luminescent MOSLED host material in Table 5, retrieve the ALD process parameters from Table 3 and report alongside EQE.  
Detailed: For each luminescent MOSLED host material listed in Table 5 of the article, retrieve the corresponding ALD process parameters from Table 3 — metal precursor, co-reactant, growth-per-cycle rate (GPC), and deposition temperature — and report them alongside the external quantum efficiency (EQE). The result must be returned as one single table only, in CSV format, with one row per result, and with the following columns: matrix, process_material, eqe, metal_precursor, co_reactant, gpc, temp.  
SPARQL: https://tinyurl.com/t3t5-complex

#### 18. Tables 3 and 5 (complex query 2)  
Short: Which rare-earth oxide matrices share synthesis (Table 3) and device performance (Table 5), and how do synthesis/annealing conditions relate to efficiencies and lifetimes?  
Detailed: Please provide the synthesis temperature from Table 3 and the annealing temperature, external quantum efficiency (EQE), power efficiency, and emission lifetime from Table 5 for each rare-earth oxide matrix that appears in both tables. The result must be returned as one single table only, in CSV format, with one row per result, and with the following columns: matrix, synthesis_temp, annealing_temp, eqe, power_eff, lifetime.  
SPARQL: https://tinyurl.com/t3t5-correlation  

#### 19. Tables 2, 3, and 5 (complex query)
Short: From Table 2, select Er-doped luminescent oxides. Combine synthesis temperatures (Table 3) and EQEs (Table 5) and compute: efficiency index = EQE / synthesis temperature × 100. Rank materials by this index.  
Detailed: From Table 2, select oxide materials doped with Er for luminescence. Combine their synthesis temperatures from Table 3 and EQEs from Table 5, then compute an efficiency index = (EQE / synthesis temperature × 100) to identify materials that deliver high efficiency at lower fabrication temperatures. Rank materials by this index. The result must be returned as exactly one table only, in CSV format, with one row per result, and with the following columns: material, synthesis_temp, eqe, efficiency_index.  
SPARQL: https://tinyurl.com/t2t3t5-complex  

---

# ALE

## Paper 1
**Atomic Layer Etching at the Tipping Point: An Overview**  
https://doi.org/10.1149/2.0061506jss

### Table I (R1562672)
https://orkg.org/comparisons/R1562672

#### 1. NL easy query  
For each ALE investigation, list the material, adsorption precursor chemistry, and energy source.  
SPARQL: https://tinyurl.com/orkg-ale-materials-nolimit 

#### 2. NL complex query  
Group ALE materials by dominant energy-source category (neutral beam, plasma ions, photon, thermal) and count distinct precursor chemistries.  
SPARQL: https://tinyurl.com/ale-energy-classes

---

## Paper 2
**Thermal atomic layer etching: A review**  
https://doi.org/10.1116/6.0000894

### Table III (R1563034)
https://orkg.org/comparisons/R1563034

#### 3. NL easy query  
List, for each material etched, the distinct reactant tuples (Reactant 1–3) and how many entries report each tuple. 
SPARQL: https://tinyurl.com/t3-easy-ale

#### 4. NL complex query  
Classify each thermal ALE chemistry by archetype (Fluorination + ligand-exchange, Oxidation + chelation, Halogenation & conversion, Other) and count chemistries and materials per archetype. 
SPARQL: https://tinyurl.com/t3-mechanism-buckets

---

## Paper 3
**Thermal atomic layer etching: Mechanism, materials and prospects**  
https://doi.org/10.1016/j.pnsc.2018.11.003

### Table 3 (R1560222)
https://orkg.org/comparisons/R1560222

#### 5. NL easy query  
List all thermal ALE processes with EPC > 0.5 Å/cycle; return material, reactants, EPC, and etching temperature; sort by EPC. 
SPARQL: https://tinyurl.com/t3-easy-fang

#### 6. NL complex query  
Group all thermal ALE processes by mechanism archetype and compute distinct materials and mean EPC per group.  
SPARQL: https://tinyurl.com/t3-complex-fang

---

## Paper 4
**Physical and chemical effects in directional atomic layer etching**  
https://doi.org/10.1088/1361-6463/ab6d94

### Table 1 (R1560825)
https://orkg.org/comparisons/R1560825

#### 7. NL easy query  
List all semiconductor ALE processes and return modification, removal, and activation types; sort by activation mode.  
SPARQL: https://tinyurl.com/t1-semi-ale

#### 8. NL complex query  
Group semiconductor ALE processes by activation type and count materials per modification–removal pair.
SPARQL: https://tinyurl.com/t1-sang-complex

---

## Paper 5
**Anisotropic/Isotropic Atomic Layer Etching of Metals**  
https://doi.org/10.5757/ASCT.2020.29.3.041

### Table 2 (R1563131)
https://orkg.org/comparisons/R1563131

#### 9. NL easy query  
List all metal ALE processes with EPC ≥ 2 Å/cycle; return material, direction, modification/removal chemistry, EPC, process temperature, and cycle time; sort by EPC.
SPARQL: https://tinyurl.com/t2-metals-high-epc

#### 10. NL complex query  
Group metal ALE processes by direction and compute number of metals and mean EPC per group; sort by mean EPC. 
SPARQL: https://tinyurl.com/t2-metals-complex

---

## Paper 6
**Atomic Layer Etching of SiO₂ for Nanoscale Semiconductor Devices: A Review**  
https://doi.org/10.5757/ASCT.2024.33.1.1

### 11. Cross-table NL easy query  
#### Tables I & II  
https://orkg.org/comparisons/R1560949  
https://orkg.org/comparisons/R1560977

For each fluorocarbon precursor system appearing in both tables, list precursor chemistries, removal gas, process temperature, etching rate, and ion-energy window (RT ±20 °C), sorted by etching rate.
SPARQL: https://tinyurl.com/pap6-crossq1-easy

---

### 12. Cross-table NL easy query  
#### Tables III & IV  
https://orkg.org/comparisons/R1561025  
https://orkg.org/comparisons/R1561023

Collect all anisotropic SiO₂ ALE processes based on C₄F₈/Ar plasma across both tables; list target selectivity pair, selectivity range, chamber-wall treatment, and etch rate; sort by etch rate.
SPARQL: https://tinyurl.com/pap6-crossq2-easy

---

### 13. Cross-table NL complex query  
#### Tables I, II, III  

Group anisotropic SiO₂ ALE processes by fluorocarbon precursor family (e.g. C₄F₈, CHF₃, C₃F₇OCH₃ isomers) and compute mean/max etching rate, union of ion-energy windows, and max selectivity.
SPARQL: https://tinyurl.com/pap6-crossq1-complex

---

### 14. Cross-table NL complex query  
#### Tables V & VI  
https://orkg.org/comparisons/R1561046  
https://orkg.org/comparisons/R1562478

Combine all isotropic SiO₂ ALE processes and group by mechanism class; report number of variants, min/max/mean etching rate, temperature range, and plasma requirement.
SPARQL: https://tinyurl.com/pap6-crossq2-complex-fixed
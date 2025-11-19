# Machine-Actionable ALD & ALE Review Tables (ORKG Comparisons)

This repository contains the **source review papers** whose tables were converted into **machine-actionable ORKG Comparisons** as part of a neurosymbolic knowledge modeling effort for **Atomic Layer Deposition (ALD)** and **Atomic Layer Etching (ALE)**.

For each paper, we list:
- The paper DOI  
- The ORKG comparison(s) generated from its tables  
- Natural-language (NL) queries used for analysis  
- SPARQL query URLs that open directly in the ORKG Visual SPARQL Editor (`https://orkg.org/sparql/`)  

---

# ALD Papers

## Paper 1  
**Saturation profile based conformality analysis for atomic layer deposition: aluminum oxide in lateral high-aspect-ratio channels**  
DOI: https://doi.org/10.1039/D0CP03358H  

**Table 2 ORKG Comparison:**  
https://orkg.org/comparisons/R1469158

**Queries**

| Type | NL Query | SPARQL |
|------|----------|---------|
| Easy | Show all reactor × LHAR combinations and count frequencies. | https://tinyurl.com/lhr-reactor |
| Complex | At 300 °C in PillarHall-3, what cTMA values were reported? | https://tinyurl.com/pillarhall3-ctm |

---

## Paper 2  
**Atomic layer deposition on particulate materials from 1988 through 2023**  
DOI: https://doi.org/10.48550/arXiv.2506.17725  

### Table 3  
https://orkg.org/comparisons/R1469383

| Type | NL Query | SPARQL |
|------|----------|---------|
| Easy | Which phosphors were coated with SiO₂? | https://tinyurl.com/Phosphor-SiO2-ALD |
| Complex | Eu²⁺ red phosphors with ≤150 °C, ≤20 nm coatings; list precursor schemes. | https://tinyurl.com/Red-Eu2-ALD-thinlowT |

### Table 4  
https://orkg.org/comparisons/R1469594

| Type | NL Query | SPARQL |
|------|----------|---------|
| Easy | Which supports were coated at ≤40 °C and with which precursor pairs? | https://tinyurl.com/less-than-40 |
| Complex | Thin (<20 nm), low-T (<70 °C) coatings; classify Al₂O₃ GPC. | https://tinyurl.com/pharma-hard-query |

---

## Paper 3  
**Atomic and Molecular Layer Deposition of Functional Thin Films Based on Rare Earth Elements**  
DOI: https://doi.org/10.1002/admi.202400274  

### Table 2  
https://orkg.org/comparisons/R1469955

| Type | NL Query | SPARQL |
|------|----------|---------|
| Easy | Most versatile rare-earth dopants per application. | https://tinyurl.com/versatile-dopants |
| Complex | Host materials appearing in multiple application domains. | https://tinyurl.com/cross-functional-hosts |

### Table 3  
https://orkg.org/comparisons/R1471077

| Type | NL Query | SPARQL |
|------|----------|---------|
| Easy | Rare-earth ALD processes with GPC ≥ 1 Å at ≤250 °C. | https://tinyurl.com/ald-highgpc-lowtemp |
| Complex | Y₂O₃: compare GPC for thermal vs PE-ALD. | https://tinyurl.com/ald-y2o3-gpc200 |

### Table 4  
https://orkg.org/comparisons/R1470110

| Type | NL Query | SPARQL |
|------|----------|---------|
| Easy | Hybrid films with GPC ≥ 5 Å at ≤250 °C. | https://tinyurl.com/HiGLoT-query |
| Complex | Average GPC per organic linker family (≤250 °C). | https://tinyurl.com/aldmld-linker-gpc |

### Table 5  
https://orkg.org/comparisons/R1469991

| Type | NL Query | SPARQL |
|------|----------|---------|
| Easy | Er³⁺ MOSLEDs with EQE ≥ 10% at lowest threshold voltage. | https://tinyurl.com/mosled-high-eqe |
| Complex | Rank hosts by EQE-per-Volt score. | https://tinyurl.com/mosled-pareto-score |

### Cross-Table Queries (Tables 2–5)

| Scope | Description | SPARQL |
|--------|-------------|---------|
| Tables 3 + 5 | Join ALD recipes with MOSLED performance. | https://tinyurl.com/t3t5-lowT |
| Tables 2 + 5 | Luminescent materials that also have MOSLED data. | https://tinyurl.com/LumMOSLED-query |
| Tables 3 + 5 | ALD parameters + MOSLED EQE for each host. | https://tinyurl.com/t3t5-complex |
| Tables 3 + 5 | Process–performance correlations. | https://tinyurl.com/t3t5-correlation |
| Tables 2 + 3 + 5 | Compute efficiency index = EQE / synthesis temp ×100. | https://tinyurl.com/t2t3t5-complex |

---

# ALE Papers

## Paper 1  
**Atomic Layer Etching at the Tipping Point: An Overview**  
DOI: https://doi.org/10.1149/2.0061506jss  
**Table I:** https://orkg.org/comparisons/R1562672

| Type | NL Query | SPARQL |
|------|----------|---------|
| Easy | List materials, adsorption precursor, and energy source. | https://tinyurl.com/orkg-ale-materials |
| Complex | Group ALE materials by energy-source category. | https://tinyurl.com/ale-energy-classes |

---

## Paper 2  
**Thermal atomic layer etching: A review**  
DOI: https://doi.org/10.1116/6.0000894  
**Table III:** https://orkg.org/comparisons/R1563034

| Type | NL Query | SPARQL |
|------|----------|---------|
| Easy | Distinct reactant tuples and counts. | https://tinyurl.com/t3-easy-ale |
| Complex | Classify chemistries by mechanistic archetype. | https://tinyurl.com/t3-mechanism-buckets |

---

## Paper 3  
**Thermal atomic layer etching: Mechanism, materials and prospects**  
DOI: https://doi.org/10.1016/j.pnsc.2018.11.003  
**Table 3:** https://orkg.org/comparisons/R1560222

| Type | NL Query | SPARQL |
|------|----------|---------|
| Easy | Thermal ALE with EPC > 0.5 Å/cycle. | https://tinyurl.com/t3-easy-fang |
| Complex | Group by mechanism; compute mean EPC. | https://tinyurl.com/t3-complex-fang |

---

## Paper 4  
**Physical and chemical effects in directional atomic layer etching**  
DOI: https://doi.org/10.1088/1361-6463/ab6d94  
**Table 1:** https://orkg.org/comparisons/R1560825

| Type | NL Query | SPARQL |
|------|----------|---------|
| Easy | List semiconductor ALE processes; modification/removal/activation. | https://tinyurl.com/t1-semi-ale |
| Complex | Group by activation and count materials. | https://tinyurl.com/t1-sang-complex |

---

## Paper 5  
**Anisotropic/Isotropic Atomic Layer Etching of Metals**  
DOI: https://doi.org/10.5757/ASCT.2020.29.3.041  
**Table 2:** https://orkg.org/comparisons/R1563131

| Type | NL Query | SPARQL |
|------|----------|---------|
| Easy | Metal ALE with EPC ≥ 2 Å/cycle. | https://tinyurl.com/t2-metals-high-epc |
| Complex | Group metals by direction; compute mean EPC. | https://tinyurl.com/t2-metals-complex |

---

## Paper 6  
**Atomic Layer Etching of SiO₂ for Nanoscale Semiconductor Devices**  
DOI: https://doi.org/10.5757/ASCT.2024.33.1.1  

### Tables I & II  
https://orkg.org/comparisons/R1560949  
https://orkg.org/comparisons/R1560977

| Type | NL Query | SPARQL |
|------|----------|---------|
| Easy | Fluorocarbon systems appearing in both tables near RT. | https://tinyurl.com/pap6-crossq1-easy |

### Tables III & IV  
https://orkg.org/comparisons/R1561025  
https://orkg.org/comparisons/R1561023

| Type | NL Query | SPARQL |
|------|----------|---------|
| Easy | C₄F₈/Ar anisotropic processes with selectivity and etch rate. | https://tinyurl.com/pap6-crossq2-easy |

### Complex Cross-Table Queries

| Scope | SPARQL |
|--------|---------|
| Tables I–III | https://tinyurl.com/pap6-crossq1-complex |
| Tables V–VI | https://tinyurl.com/pap6-crossq2-complex |



Please extract data from Table 5 of the article titled "Atomic and Molecular Layer Deposition of Functional Thin Films Based on Rare Earth Elements" with DOI 10.1002/admi.202400274.

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

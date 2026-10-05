# Coverage report — what the model omits

**Model:** `Qwen/Qwen2.5-1.5B-Instruct`  
**Graph:** Hetionet v1.0 (Himmelstein et al. 2017), used as-is  
**Subjects:** 20, sampled with seed 7 from edges with 5–60 targets

Every number below is a count over graph edges. No judge model, no entailment score, no learned metric.

## Headline

| Measure | Value |
| --- | ---: |
| Facts the graph holds | 427 |
| Facts the model stated | 597 |
| Correct (in graph) | 11 |
| **Coverage** (of graph knowledge surfaced) | **2.6%** |
| **Precision** (of statements that were real) | **1.8%** |
| Subjects with ZERO correct facts | 15/20 |

## How to verify any row yourself

The graph side of every row is reproducible without this script and without trusting anything an LLM said:

```bash
# all true targets for one subject (substitute the subject id)
gunzip -c data/hetionet/edges.sif.gz \
  | awk -F'\t' '$1=="Compound::DB00997" && $2=="CbG"' \
  | cut -f3 > ids.txt
# map those ids to names
grep -F -f ids.txt data/hetionet/nodes.tsv | cut -f1,2
```

## Rows

### Nitrofural — downregulates (`Compound::DB00336`, `CdG`)

**Question:** List every gene that the compound Nitrofural downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
NRNH1, NRNF2, NRNGT1, NRNSC1, NRNTL1, NRNU3, NRNV1, NRNX1, NRNY1, NRNZ1, NRNTN1, NRNTS1, NRNTU1, NRNTV1, NRNTW1, NRNTX1, NRNTY1, NRNTZ1, NRNTA1, NRNTB1, NRNTC1, NRNTD1, NRNET1, NRNEF1, NRNEG1, NRNEH1, NRNEI1, NRNEJ1, NRNEK1, NRNEL1, NRNEM1, NRNEY1, NRNEZ1, NRNEA1, NRNEB1, NRNEC1, NREN1, NRNEE1, NRNEF1, NRNEG1, NRNEH1, NRNEI1, NRNEJ1, NRNEK1, NRNEL1, NRNEM1, NRNEY1, NRNEZ1, NRNEA1, NRNEB1, NRNEC1, NREN1, NRNEE1, NRNEF1, NRNEG1, NRNEH1, NRNEI1, NRNEJ1, NRNEK1, NRNEL1, NRNEM1, NRNEY1, NRNEZ1, NRNEA
```

- Graph holds **12** facts; model stated **64**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): NRNH1, NRNF2, NRNGT1, NRNSC1, NRNTL1, NRNU3, NRNV1, NRNX1, NRNY1, NRNZ1, NRNTN1, NRNTS1, NRNTU1, NRNTV1, NRNTW1
- Missed: CRYZ, DDAH1, HDAC2, ISOC1, ITGAE, ITGB1BP1, KIF20A, NVL, PPP2R5E, S100A6, TMEM50A, TXNDC9

### Quinidine — binds (`Compound::DB00908`, `CbG`)

**Question:** List every gene that the compound Quinidine binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
KCNQ1, KCNH2, SCN5A
```

- Graph holds **29** facts; model stated **3**; **2** were correct.
- Coverage **6.9%**, precision **66.7%**
- Correct: KCNH2, SCN5A
- Invented (not in graph): KCNQ1
- Missed: ABCB1, ABCB11, ABCC2, CHRM2, CYP1A1, CYP1A2, CYP2B6, CYP2C8, CYP2C9, CYP2D6, CYP2E1, CYP3A4, CYP3A7, CYP3A7-CYP3A51P, KCNK1, KCNK6, ORM1, SCN1A, SCN2A, SCN3A, SLC22A1, SLC22A2, SLC22A4, SLC22A5, SLC22A8 …

### Flutamide — downregulates (`Compound::DB00499`, `CdG`)

**Question:** List every gene that the compound Flutamide downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
AR, ERα, PR
```

- Graph holds **10** facts; model stated **3**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): AR, ERα, PR
- Missed: ADI1, ATP6V1D, CCNB1, GNAS, HMGCR, HMGCS1, INSIG1, KDM3A, MBOAT7, PCNA

### Fenofibrate — upregulates (`Compound::DB01039`, `CuG`)

**Question:** List every gene that the compound Fenofibrate upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ACAT1, ACACA, ACSL3, CYP7A1, FASN, HMGCR, MGAT5B, MGAT6, MGAT8, MGAT9, MGAT10, MGAT12, MGAT14, MGAT15, MGAT16, MGAT17, MGAT18, MGAT19, MGAT2, MGAT3, MGAT4A, MGAT4B, MGAT4C, MGAT4D, MGAT4E, MGAT4F, MGAT4G, MGAT4H, MGAT4I, MGAT4J, MGAT4K, MGAT4L, MGAT4M, MGAT4N, MGAT4O, MGAT4P, MGAT4Q, MGAT4R, MGAT4S, MGAT4T, MGAT4U, MGAT4V, MGAT4W, MGAT4X, MGAT4Y, MGAT4Z, MGAT5, MGAT6, MGAT7, MGAT8, MGAT9, MGAT10, MGAT11, MGAT12, MGAT13, MGAT14, MGAT15, MGAT16, MGAT17, MGAT18, MGAT19, MGAT2, MGAT3, MGAT4
```

- Graph holds **8** facts; model stated **64**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ACAT1, ACACA, ACSL3, CYP7A1, FASN, HMGCR, MGAT5B, MGAT6, MGAT8, MGAT9, MGAT10, MGAT12, MGAT14, MGAT15, MGAT16
- Missed: CSTA, HLA-DRA, HTRA1, IL4R, KIT, MAP7, NR1H2, SOX2

### Bortezomib — binds (`Compound::DB00188`, `CbG`)

**Question:** List every gene that the compound Bortezomib binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
BNUB1, TNFRSF17
```

- Graph holds **17** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): BNUB1, TNFRSF17
- Missed: CTSG, CYP1A1, CYP1A2, CYP2C19, CYP2C8, CYP2C9, CYP2D6, CYP3A4, PSMA1, PSMB1, PSMB2, PSMB5, PSMB8, PSMD1, PSMD2, PTGS1, SLC31A1

### Ergocalciferol — binds (`Compound::DB00153`, `CbG`)

**Question:** List every gene that the compound Ergocalciferol binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
RORα, RORγ2
```

- Graph holds **7** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): RORα, RORγ2
- Missed: AR, CYP24A1, CYP27A1, CYP27B1, CYP2R1, CYP3A4, VDR

### Prednicarbate — upregulates (`Compound::DB01130`, `CuG`)

**Question:** List every gene that the compound Prednicarbate upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
EPAS1, ANGPTL4, CYP2C9, CYP3A5, CYP3A7, CYP3A8, CYP3A9, CYP3A10, CYP3A11, CYP3A12, CYP3A13, CYP3A14, CYP3A15, CYP3A16, CYP3A17, CYP3A18, CYP3A19, CYP3A20, CYP3A21, CYP3A22, CYP3A23, CYP3A24, CYP3A25, CYP3A26, CYP3A27, CYP3A28, CYP3A29, CYP3A30, CYP3A31, CYP3A32, CYP3A33, CYP3A34, CYP3A35, CYP3A36, CYP3A37, CYP3A38, CYP3A39, CYP3A40, CYP3A41, CYP3A42, CYP3A43, CYP3A44, CYP3A45, CYP3A46, C
```

- Graph holds **8** facts; model stated **45**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): EPAS1, ANGPTL4, CYP2C9, CYP3A5, CYP3A7, CYP3A8, CYP3A9, CYP3A10, CYP3A11, CYP3A12, CYP3A13, CYP3A14, CYP3A15, CYP3A16, CYP3A17
- Missed: IKBKB, PEX11A, PRR15L, RAB27A, SERPINA3, SSBP2, TSC22D3, WASF3

### Calcitriol — downregulates (`Compound::DB00136`, `CdG`)

**Question:** List every gene that the compound Calcitriol downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
VDR, CYP24A1
```

- Graph holds **19** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): VDR, CYP24A1
- Missed: CCDC86, CCL2, CD320, GAS2L1, GNB5, HPRT1, IER3, LRPAP1, MYC, NT5DC2, NUCB2, NUP85, PLA2G15, PPP2R5E, PRPF4, RPIA, RRP1B, SH3BP5, UTP18

### Escitalopram — binds (`Compound::DB01175`, `CbG`)

**Question:** List every gene that the compound Escitalopram binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
DYSMC1, CYP2C19, COMT, MAO-B, HTR2A, HTR2B, HTR3A, HTR3B, HTR4, HTR5A, HTR6, HTR7, HTR8S1, HTR8S2, HTR9, GABRA5, GABRB3, GABRG2, GABRR2, GABRQ, GABRD, GABRA2, GABRA3, GABRA4, GABRA5, GABRB1, GABRC1, GABRG1, GABRR1, GABRS1, GABRS2, GABRS3, GABRT, GABRU, GABSS, GABSN, GABTA, GABTB, GABTC, GABTD, GABTE, GABTT, GABTU, GABTV, GABTW, GABTX, GABTY, GABTZ, GABU, GABV, GABW, GABX, GABY, GABZ, GABAA, GABAB, GABAC, GABAD, GABAE, GABAF, GABAG, GABAH, GABAI, GABAJ, GABAK, GABAL, GABAM, GABAN,
```

- Graph holds **10** facts; model stated **68**; **1** were correct.
- Coverage **10.0%**, precision **1.5%**
- Correct: CYP2C19
- Invented (not in graph): DYSMC1, COMT, MAO-B, HTR2A, HTR2B, HTR3A, HTR3B, HTR4, HTR5A, HTR6, HTR7, HTR8S1, HTR8S2, HTR9, GABRA5
- Missed: ADRA1A, CHRM1, CYP2D6, CYP3A4, HRH1, HTR2C, SLC6A2, SLC6A3, SLC6A4

### Phenobarbital — binds (`Compound::DB01174`, `CbG`)

**Question:** List every gene that the compound Phenobarbital binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
BTAACGATCTTCTCAGGGTGGAATGCCAATGTCTCTTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCTTCT
```

- Graph holds **28** facts; model stated **0**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): (none)
- Missed: ABCB1, ABCB11, ABCC1, ABCC2, ABCC3, CHRFAM7A, CHRNA4, CHRNA7, CYP1A1, CYP1A2, CYP1B1, CYP2A6, CYP2B6, CYP2C18, CYP2C19, CYP2C8, CYP2C9, CYP2E1, CYP3A4, CYP3A5, CYP3A7, CYP3A7-CYP3A51P, CYP4A11, CYP4B1, GABRA1 …

### Colchicine — downregulates (`Compound::DB01394`, `CdG`)

**Question:** List every gene that the compound Colchicine downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TUBB3, TUBA1C, TUBB4, TUBB5, TUBB6, TUBB7, TUBB8, TUBB9, TUBB10, TUBB11, TUBB12, TUBB13, TUBB14, TUBB15, TUBB16, TUBB17, TUBB18, TUBB19, TUBB20, TUBB21, TUBB22, TUBB23, TUBB24, TUBB25, TUBB26, TUBB27, TUBB28, TUBB29, TUBB30, TUBB31, TUBB32, TUBB33, TUBB34, TUBB35, TUBB36, TUBB37, TUBB38, TUBB39, TUBB40, TUBB41, TUBB42, TUBB43, TUBB44, TUBB45, TUBB46, TUBB47, TUBB48, TUBB49, TUBB50, TUBB51, TUBB52, T
```

- Graph holds **44** facts; model stated **52**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): TUBB3, TUBA1C, TUBB4, TUBB5, TUBB6, TUBB7, TUBB8, TUBB9, TUBB10, TUBB11, TUBB12, TUBB13, TUBB14, TUBB15, TUBB16
- Missed: ADH5, AKR7A2, B4GAT1, BET1, C1RL, C2CD5, CCNE2, CDK1, CHEK2, COPS7A, CPNE3, DTL, EAPP, ESR1, FIS1, GATA3, GNPDA1, GOLPH3L, HADH, HIST1H2BK, HSPA1A, ISOC1, MAT2B, MCM3, MCM6 …

### Ethacrynic acid — upregulates (`Compound::DB00903`, `CuG`)

**Question:** List every gene that the compound Ethacrynic acid upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ABCC2
```

- Graph holds **26** facts; model stated **1**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ABCC2
- Missed: ABCB6, ABHD4, AKR1C1, AKR1C2, CBR1, CDKN1A, CTSL, FAS, FOSL1, GCLM, GPC1, HMOX1, INPP1, KEAP1, KIAA0355, LRP10, MVP, P4HA2, PRSS23, RAP1GAP, RRP8, SESN1, SQSTM1, TMEM2, TXNRD1 …

### Cyclophosphamide — downregulates (`Compound::DB00531`, `CdG`)

**Question:** List every gene that the compound Cyclophosphamide downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TP53, BRCA1, BRCA2, CHEK2, ATM, CDKN2A, PTEN, TP53BP2, PPM1D, PIK3R4, PIK3CD, PIK3CG, PIK3CB, PIK3CA, AKT1, AKT2, AKT3, ERBB2, EGFR, MET, KRAS, NRAS, HRAS, FLT3, FGFR1, FGFR2, FGFR3, FGFR4, IGF1R, JAK2, JAK3, TYRO3, TRA2B, VEGFA, VEGFBC, VEGFD, VEGFRA, VEGFB, VEGFC, VEGFD, VEGFE, VEGFF, VEGFG, VEGFH, VEGFI, VEGFK, VEGFL, VEGFM, VEGFN, VEGFO, VEGFP, VEGFS, VEGFT, VEGFU, VEGFY, VEGFZ, VEGFX, VEGFY, VEGFZ, VEGFX, VEGFY, VEGFZ, VEGFX, VEGFY, VEGFZ, VEGFX, VEGFY, VEGFZ, VEGFX, VEGFY, VEGFZ, VEGFX, VEG
```

- Graph holds **11** facts; model stated **73**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): TP53, BRCA1, BRCA2, CHEK2, ATM, CDKN2A, PTEN, TP53BP2, PPM1D, PIK3R4, PIK3CD, PIK3CG, PIK3CB, PIK3CA, AKT1
- Missed: ADI1, ATP6V0B, CDK4, CHMP4A, CNDP2, DLD, EBNA1BP2, ENOPH1, MTHFD2, S100A13, USP22

### Pazopanib — upregulates (`Compound::DB06589`, `CuG`)

**Question:** List every gene that the compound Pazopanib upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
VEGFR2, VEGFR1, PDGFRB, FGFR3
```

- Graph holds **59** facts; model stated **4**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): VEGFR2, VEGFR1, PDGFRB, FGFR3
- Missed: ANXA7, ATP5S, BCL7B, CBX3, CDCA4, CGRRF1, CHEK2, CPVL, CRIP1, CXCL8, CYTH1, EBNA1BP2, EIF4EBP1, FAM216A, FKBP14, FOXJ3, GLOD4, GSS, ICAM3, IER3, IL1R2, KIAA0355, LPL, LYPLA1, LYRM1 …

### Tacrolimus — upregulates (`Compound::DB00864`, `CuG`)

**Question:** List every gene that the compound Tacrolimus upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TCF7L2, TNFRSF10B, IL2RG, CDKAL1, FAS, TCF7L1, TNFSF13B
```

- Graph holds **9** facts; model stated **7**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): TCF7L2, TNFRSF10B, IL2RG, CDKAL1, FAS, TCF7L1, TNFSF13B
- Missed: AXIN1, CCNA1, DDIT4, LPL, PRKAG2, SQRDL, ST6GALNAC2, TLR4, TSC22D3

### malaria — associates (`Disease::DOID:12365`, `DaG`)

**Question:** List every gene associated with the disease malaria. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
PF3C, TOM40, DHPR, NSN, PFC2A1, PFC2B1, PFC2B2, PFC2B3, PFC2B4, PFC2B5, PFC2B6, PFC2B7, PFC2B8, PFC2B9, PFC2B10, PFC2B11, PFC2B12, PFC2B13, PFC2B14, PFC2B15, PFC2B16, PFC2B17, PFC2B18, PFC2B19, PFC2B20, PFC2B21, PFC2B22, PFC2B23, PFC2B24, PFC2B25, PFC2B26, PFC2B27, PFC2B28, PFC2B29, PFC2B30, PFC2B31, PFC2B32, PFC2B33, PFC2B34, PFC2B35, PFC2B36, PFC2B37, PFC2B38, PFC2B39, PFC2B40, PFC2B41, PFC
```

- Graph holds **49** facts; model stated **47**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): PF3C, TOM40, DHPR, NSN, PFC2A1, PFC2B1, PFC2B2, PFC2B3, PFC2B4, PFC2B5, PFC2B6, PFC2B7, PFC2B8, PFC2B9, PFC2B10
- Missed: ABO, ACKR1, CD36, CD4, CD40LG, CD8A, CISH, CR1, CRP, DECR1, DHFR, DHODH, FAS, FCGR2A, FCGR2B, G6PD, GYPA, GYPC, HBB, HLA-B, HP, HPGDS, ICAM1, IFNG, IL10 …

### Paget's disease of bone — associates (`Disease::DOID:5408`, `DaG`)

**Question:** List every gene associated with the disease Paget's disease of bone. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
PTPN22, TNFSF10, TNFRSF11B, TRAF3, MAPK8, MAPK14, IRAK1, IRF5, STAT1, STAT3, STAT6, JAK1, JAK2, JAK3, TYK2, BCL11A, CCR9, CXCR4, FOS, JUN, MITF, NRAS, RAC1, RAF1, BRAF, KRAS, HRAS, PIK3CA, PIK3R1, PIK3CD, PIK3CG, PIK3R3, PIK3R4, PTEN, TP53, TSC1, TSC2, STK17B, SMAD4, SMAD3, SMAD2, SMAD1, SMAD7, SMAD9, SMAD10, SMAD11, SMAD12, SMAD13, SMAD14, SMAD15, SMAD16, SMAD17, SMAD18, SMAD19, SMAD20, SMAD21, SMAD22, SMAD23, SMAD24, SMAD25, SMAD26, SMAD27, SMAD28, SMAD29, SMAD30, SMAD31, SMAD32, SM
```

- Graph holds **16** facts; model stated **68**; **1** were correct.
- Coverage **6.2%**, precision **1.5%**
- Correct: TNFRSF11B
- Invented (not in graph): PTPN22, TNFSF10, TRAF3, MAPK8, MAPK14, IRAK1, IRF5, STAT1, STAT3, STAT6, JAK1, JAK2, JAK3, TYK2, BCL11A
- Missed: ALPL, ALPP, ALPPL2, BGLAP, CALCA, CSF1, DCSTAMP, INPP5D, NUP205, OPTN, PML, RIN3, SQSTM1, TNFRSF11A, VCP

### attention deficit hyperactivity disorder — associates (`Disease::DOID:1094`, `DaG`)

**Question:** List every gene associated with the disease attention deficit hyperactivity disorder. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ACSN1, ADH1B, ADCY8, ANK3, BDNF, CHRNA7, CNTNAP2, DAB1, DISC1, DRD4, EFNA5, FMRP, GAD1, GRM6, HTR2A, KCNJ2, KCTD10, LMX1A, MAPT, MEG3, NRG1, NRXN1, OPN1SW, PDE4DIP, PRDM16, RAI1, SCN1A, SCN9A, SLC6A4, TPH2, UBE3A, VPS13C, WDR45
```

- Graph holds **41** facts; model stated **33**; **6** were correct.
- Coverage **14.6%**, precision **18.2%**
- Correct: ANK3, BDNF, DRD4, HTR2A, SLC6A4, TPH2
- Invented (not in graph): ACSN1, ADH1B, ADCY8, CHRNA7, CNTNAP2, DAB1, DISC1, EFNA5, FMRP, GAD1, GRM6, KCNJ2, KCTD10, LMX1A, MAPT
- Missed: ADRA2A, ADRA2C, AS3MT, CACNA1C, CACNB2, CCDC68, CHRNA4, COMT, CSMD1, DPYD, DRD1, DRD2, DRD3, DRD5, EFS, EP300, GABRQ, GRM7, HRH3, HTR1B, IMPACT, ITIH3, MAOA, MB21D1, MMP16 …

### Fuchs' endothelial dystrophy — associates (`Disease::DOID:11555`, `DaG`)

**Question:** List every gene associated with the disease Fuchs' endothelial dystrophy. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
FUCHS ENDOTHELIAL DYSTROPHY, FED, FED1, FED2, FED3, FED4, FED5, FED6, FED7, FED8, FED9, FED10
```

- Graph holds **6** facts; model stated **12**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): FUCHS ENDOTHELIAL DYSTROPHY, FED, FED1, FED2, FED3, FED4, FED5, FED6, FED7, FED8, FED9, FED10
- Missed: COL8A1, COL8A2, FBXO7, ITGBL1, PTPRG, TCF4

### gout — associates (`Disease::DOID:13189`, `DaG`)

**Question:** List every gene associated with the disease gout. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
HMGCR, LCAT, APOB, HSD3B7, ABCG2, SLC25A4, FURIN, ADAMTS1, ALDH1A3, CYP2C9, CYP2C8, CYP2C6, CYP2C19, CYP2D6, CYP2E1, CYP2C10, CYP2C2, CYP2C1, CYP2C3, CYP2C4, CYP2C5, CYP2C7, CYP2C9_2, CYP2C10_2, CYP2C11, CYP2C12, CYP2C13, CYP2C14, CYP2C15, CYP2C16, CYP2C17, CYP2C18, CYP2C19_2, CYP2C20, CYP2C21, CYP2C22, CYP2C23, CYP2C24, CYP2C25, CYP2C26, CYP2C27, CYP2C28, CYP2C29, CYP2C30, CYP2C31, CYP2C32, CYP2C
```

- Graph holds **18** facts; model stated **47**; **1** were correct.
- Coverage **5.6%**, precision **2.1%**
- Correct: ABCG2
- Invented (not in graph): HMGCR, LCAT, APOB, HSD3B7, SLC25A4, FURIN, ADAMTS1, ALDH1A3, CYP2C9, CYP2C8, CYP2C6, CYP2C19, CYP2D6, CYP2E1, CYP2C10
- Missed: ALDH16A1, BCKDHA, CASP1, HPRT1, IL15, IL1RN, LRRC16A, NLRP3, POMC, PRPS1, PRPS2, SLC17A1, SLC17A3, SLC22A11, SLC22A12, SLC2A9, UMOD

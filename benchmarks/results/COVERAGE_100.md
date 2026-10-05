# Coverage report — what the model omits

**Model:** `Qwen/Qwen2.5-1.5B-Instruct`  
**Graph:** Hetionet v1.0 (Himmelstein et al. 2017), used as-is  
**Subjects:** 100, sampled with seed 11 from edges with 5–60 targets

Every number below is a count over graph edges. No judge model, no entailment score, no learned metric.

## Headline

| Measure | Value |
| --- | ---: |
| Facts the graph holds | 1567 |
| Facts the model stated | 2220 |
| Correct (in graph) | 47 |
| **Coverage** (of graph knowledge surfaced) | **3.0%** |
| **Precision** (of statements that were real) | **2.1%** |
| Subjects with ZERO correct facts | 76/100 |

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

### Sulfathiazole — upregulates (`Compound::DB06147`, `CuG`)

**Question:** List every gene that the compound Sulfathiazole upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
SULT1A2, CYP3A4, CYP3A5, CYP3A7
```

- Graph holds **10** facts; model stated **4**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): SULT1A2, CYP3A4, CYP3A5, CYP3A7
- Missed: ADAT1, CASP10, CNOT4, EPHA3, NFATC3, PIGB, RBKS, ST6GALNAC2, TSEN2, WASF3

### Drospirenone — binds (`Compound::DB01395`, `CbG`)

**Question:** List every gene that the compound Drospirenone binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
NR5A1, NR5A2, NR0B1, CYP3A4, CYP3A5, CYP3A7, CYP3A8, CYP3A9, CYP3A10, CYP3A11, CYP3A12, CYP3A13, CYP3A14, CYP3A15, CYP3A16, CYP3A17, CYP3A18, CYP3A19, CYP3A20, CYP3A21, CYP3A22, CYP3A23, CYP3A24, CYP3A25, CYP3A26, CYP3A27, CYP3A28, CYP3A29, CYP3A30, CYP3A31, CYP3A32, CYP3A33, CYP3A34, CYP3A35, CYP3A36, CYP3A37, CYP3A38, CYP3A39, CYP3A40, CYP3A41, CYP3A42, CYP3A43, CYP3A44, CYP3A45, CYP3
```

- Graph holds **5** facts; model stated **45**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): NR5A1, NR5A2, NR0B1, CYP3A4, CYP3A5, CYP3A7, CYP3A8, CYP3A9, CYP3A10, CYP3A11, CYP3A12, CYP3A13, CYP3A14, CYP3A15, CYP3A16
- Missed: AR, BCHE, NR3C2, PGR, PTGS2

### Alendronate — binds (`Compound::DB00630`, `CbG`)

**Question:** List every gene that the compound Alendronate binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ALDH2, CYP2C9, CYP3A4, CYP3A5, CYP3A7, GSTP1, MTHFR, UGT1A1
```

- Graph holds **5** facts; model stated **8**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ALDH2, CYP2C9, CYP3A4, CYP3A5, CYP3A7, GSTP1, MTHFR, UGT1A1
- Missed: ATP6V1A, FDPS, PTPN4, PTPRE, PTPRS

### Pindolol — binds (`Compound::DB00960`, `CbG`)

**Question:** List every gene that the compound Pindolol binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
BETA_2_ADRENERGIC_RECEPTOR, ALPHA_1_BETA_3_GAMMA_4_RECEPTOR
```

- Graph holds **6** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): BETA_2_ADRENERGIC_RECEPTOR, ALPHA_1_BETA_3_GAMMA_4_RECEPTOR
- Missed: ADRB1, ADRB2, ADRB3, CYP2D6, HTR1A, HTR1B

### Aminohippurate — downregulates (`Compound::DB00345`, `CdG`)

**Question:** List every gene that the compound Aminohippurate downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
AHI1, ABCB8, CYP2C9, CYP3A4, CYP3A5, CYP3A7, CYP2D6, CYP2C19, CYP2C19*2, CYP2C19*3, CYP2C19*4, CYP2C19*5, CYP2C19*6, CYP2C19*7, CYP2C19*8, CYP2C19*9, CYP2C19*10, CYP2C19*11, CYP2C19*12, CYP2C19*13, CYP2C19*14, CYP2C19*15, CYP2C19*16, CYP2C19*17, CYP2C19*18, CYP2C19*19, CYP2C19*20, CYP2C19*21, CYP2C19*22, CYP2C19*23, CYP2C19*24, CYP2C19*25, CYP2C19*26, CYP2C19*27, CYP2
```

- Graph holds **5** facts; model stated **35**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): AHI1, ABCB8, CYP2C9, CYP3A4, CYP3A5, CYP3A7, CYP2D6, CYP2C19, CYP2C19*2, CYP2C19*3, CYP2C19*4, CYP2C19*5, CYP2C19*6, CYP2C19*7, CYP2C19*8
- Missed: IGFBP2, NCAPD2, NR2F6, TES, VPS28

### Quinidine barbiturate — binds (`Compound::DB01346`, `CbG`)

**Question:** List every gene that the compound Quinidine barbiturate binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
KCNQ1, KCNH2, SCN5A
```

- Graph holds **8** facts; model stated **3**; **2** were correct.
- Coverage **25.0%**, precision **66.7%**
- Correct: KCNH2, SCN5A
- Invented (not in graph): KCNQ1
- Missed: CHRM2, CYP2D6, GABRA1, GABRA2, GRIA2, KCNK1

### Sunitinib — upregulates (`Compound::DB01268`, `CuG`)

**Question:** List every gene that the compound Sunitinib upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
AKT1, AKT2, PTEN, VEGFR2, FLT3, PDGFRB, FGFR1, RAF1, BRAF, MEK1, ERBB2, KRAS, NRAS, PIK3CA, PIK3R1, PIK3CD, PIK3CG, PIK3R3, PIK3R4, PIK3CB, PIK3C3, RASGRP1, RPS6KB1, RPLP0, STK17A, TP53BP1, TSC22D3, UBE2L3, USP9Y, ZNF804A
```

- Graph holds **33** facts; model stated **30**; **1** were correct.
- Coverage **3.0%**, precision **3.3%**
- Correct: TSC22D3
- Invented (not in graph): AKT1, AKT2, PTEN, VEGFR2, FLT3, PDGFRB, FGFR1, RAF1, BRAF, MEK1, ERBB2, KRAS, NRAS, PIK3CA, PIK3R1
- Missed: AARS, ABHD4, CCDC92, CCNG2, CGRRF1, CRIP1, DDIT4, EAPP, ERBB3, FDFT1, FDPS, HBP1, HERPUD1, HMGCR, HMGCS1, IKBKB, INSIG1, KIAA0355, KLHDC2, LAMTOR3, LRP10, MSMO1, MTHFD2, NPC1, NSDHL …

### Dronabinol — binds (`Compound::DB00470`, `CbG`)

**Question:** List every gene that the compound Dronabinol binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
CB1_R3-AG, CB2_R4-AG
```

- Graph holds **10** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): CB1_R3-AG, CB2_R4-AG
- Missed: ABCB1, ABCG2, CNR1, CNR2, CYP1A1, CYP2A6, CYP2C19, CYP2C9, CYP3A4, PTGS1

### Carbamazepine — binds (`Compound::DB00564`, `CbG`)

**Question:** List every gene that the compound Carbamazepine binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
CARBAMAZEPINE_BINDER_1, CARBAMAZEPINE_BINDER_2
```

- Graph holds **16** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): CARBAMAZEPINE_BINDER_1, CARBAMAZEPINE_BINDER_2
- Missed: ABCB1, ABCC2, CYP1A2, CYP2B6, CYP2C19, CYP2C8, CYP2C9, CYP3A4, CYP3A5, CYP3A7, CYP3A7-CYP3A51P, RALBP1, SCN4A, SCN5A, SCN9A, UGT2B7

### Donepezil — upregulates (`Compound::DB00843`, `CuG`)

**Question:** List every gene that the compound Donepezil upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ARSK, CYP2B6, COMT, MAO-B, SLC6A4
```

- Graph holds **9** facts; model stated **5**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ARSK, CYP2B6, COMT, MAO-B, SLC6A4
- Missed: DNAJC15, MAPKAPK5, NFIL3, NFKBIA, PRKAG2, PRKCD, RSU1, TGFBR2, TSC22D3

### Quetiapine — downregulates (`Compound::DB01224`, `CdG`)

**Question:** List every gene that the compound Quetiapine downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
DUSP1, DUSP5, MAPK8, MAPK9, MAPK10, PTEN, PTPN22
```

- Graph holds **23** facts; model stated **7**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): DUSP1, DUSP5, MAPK8, MAPK9, MAPK10, PTEN, PTPN22
- Missed: ACAT2, ADI1, ATP6V0B, CD320, CYCS, DPYSL2, EBNA1BP2, ENOPH1, HAT1, HSPA1A, IARS2, IFRD2, ITGB1BP1, KIF1BP, NUP93, PPP2R3C, RPN1, SCAND1, TM9SF2, TMEM109, TOMM34, TXNDC9, USP22

### Alimemazine — downregulates (`Compound::DB01246`, `CdG`)

**Question:** List every gene that the compound Alimemazine downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ALDH1A2, CYP3A4, CYP3A5, CYP3A7, CYP3B4, CYP2C9, CYP2C19, CYP2D6, CYP2E1, CYP2C8, CYP2C10, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, C
```

- Graph holds **7** facts; model stated **45**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ALDH1A2, CYP3A4, CYP3A5, CYP3A7, CYP3B4, CYP2C9, CYP2C19, CYP2D6, CYP2E1, CYP2C8, CYP2C10, CYP2C19, CYP2C19, CYP2C19, CYP2C19
- Missed: CCDC86, CDC45, COG2, CYCS, DPH2, PDHX, RPIA

### Clotiazepam — binds (`Compound::DB01559`, `CbG`)

**Question:** List every gene that the compound Clotiazepam binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
CLDN10, CLCN2, CYP2C9, CYP3A4, CYP3A5, CYP3A7, CYP2D6, DHODH, GSTP1, HSD3B1, KCNJ11, KDR, LPA, MATE2K, NOS3, PON1, SLC22A1, SLC22A3, SLC22A4, SLC22A5, SLC22A6, SLC22A7, SLC22A8, SLC22A9, SLC22A10, SLC22A11, SLC22A12, SLC22A13, SLC22A14, SLC22A15, SLC22A16, SLC22A17, SLC22A18, SLC22A19, SLC22A20, SLC22A21, SLC22A22, SLC22A23, SLC22A24, SLC22A25, SLC22A26, SLC22A27, SLC22A28, SLC22A29, SLC22A30
```

- Graph holds **20** facts; model stated **45**; **1** were correct.
- Coverage **5.0%**, precision **2.2%**
- Correct: CYP3A4
- Invented (not in graph): CLDN10, CLCN2, DHODH, GSTP1, HSD3B1, KCNJ11, KDR, LPA, MATE2K, NOS3, PON1, SLC22A1, SLC22A3, SLC22A4, SLC22A5
- Missed: CYP2B6, CYP2C18, CYP2C19, GABRA1, GABRA2, GABRA3, GABRA5, GABRB1, GABRB2, GABRB3, GABRD, GABRE, GABRG1, GABRG2, GABRG3, GABRP, GABRR1, GABRR2, GABRR3

### Halofantrine — binds (`Compound::DB01218`, `CbG`)

**Question:** List every gene that the compound Halofantrine binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
AXIN2, BCL11A, CYP3A4, DHODH, DPP4, ESR1, FANCA, GNAI1, HLA-A, IL6R, KDR, LPAR1, MUC5AC, NFKB1, PDE4DIE, PTEN, RASGRP1, SLC2A9, TCF7L2, VEGFA
```

- Graph holds **5** facts; model stated **20**; **1** were correct.
- Coverage **20.0%**, precision **5.0%**
- Correct: CYP3A4
- Invented (not in graph): AXIN2, BCL11A, DHODH, DPP4, ESR1, FANCA, GNAI1, HLA-A, IL6R, KDR, LPAR1, MUC5AC, NFKB1, PDE4DIE, PTEN
- Missed: CYP2C8, CYP2D6, CYP3A5, KCNH2

### Leflunomide — binds (`Compound::DB01097`, `CbG`)

**Question:** List every gene that the compound Leflunomide binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ACO2, CYP2C19, CYP3A4, CYP3A5, CYP3A7, GSTP1, MTHFR, NUDT15, UGT2B7
```

- Graph holds **6** facts; model stated **9**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ACO2, CYP3A4, CYP3A5, CYP3A7, GSTP1, MTHFR, NUDT15, UGT2B7
- Missed: ABCG2, AHR, CYP1A2, CYP2C9, DHODH, PTK2B

### Tenofovir — downregulates (`Compound::DB00300`, `CdG`)

**Question:** List every gene that the compound Tenofovir downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
A2AR, ADRB1, ADRB2, ADRB3, ADRB4, ADRB5, ADRB6, ADRB7, ADRB8, ADRB9, ADRB10, ADRB11, ADRB12, ADRB13, ADRB14, ADRB15, ADRB16, ADRB17, ADRB18, ADRB19, ADRB20, ADRB21, ADRB22, ADRB23, ADRB24, ADRB25, ADRB26, ADRB27, ADRB28, ADRB29, ADRB30, ADRB31, ADRB32, ADRB33, ADRB34, ADRB35, ADRB36, ADRB37, ADRB38, ADRB39, ADRB40, ADRB41, ADRB42, ADRB43, ADRB44, ADRB45, ADRB46, ADRB47, ADRB48, ADRB49, ADRB50, ADRB51
```

- Graph holds **18** facts; model stated **52**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): A2AR, ADRB1, ADRB2, ADRB3, ADRB4, ADRB5, ADRB6, ADRB7, ADRB8, ADRB9, ADRB10, ADRB11, ADRB12, ADRB13, ADRB14
- Missed: ASCC3, ATP6V1D, CLTC, CNDP2, DECR1, EBNA1BP2, EIF4EBP1, GAA, LAGE3, MTHFD2, PCM1, PGAM1, PSMD9, RBM34, RPS4Y1, TSPAN3, TUFM, TXLNA

### Metocurine — binds (`Compound::DB01336`, `CbG`)

**Question:** List every gene that the compound Metocurine binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
MET, TNFRSF1A
```

- Graph holds **5** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): MET, TNFRSF1A
- Missed: CHRM2, CHRNA1, CHRNA2, CHRNB1, CHRND

### Fluvoxamine — downregulates (`Compound::DB00176`, `CdG`)

**Question:** List every gene that the compound Fluvoxamine downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
CYP2D6, CYP1A2, COMT, MAO-B, NAT2
```

- Graph holds **5** facts; model stated **5**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): CYP2D6, CYP1A2, COMT, MAO-B, NAT2
- Missed: AKR1B10, HERPUD1, OXA1L, PFN1, TUBB6

### Thiamine — binds (`Compound::DB00152`, `CbG`)

**Question:** List every gene that the compound Thiamine binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
THAP1, THAP2, THAP3, THAP4, THAP5, THAP6, THAP7, THAP8, THAP9, THAP10, THAP11, THAP12, THAP13, THAP14, THAP15, THAP16, THAP17, THAP18, THAP19, THAP20, THAP21, THAP22, THAP23, THAP24, THAP25, THAP26, THAP27, THAP28, THAP29, THAP30, THAP31, THAP32, THAP33, THAP34, THAP35, THAP36, THAP37, THAP38, THAP39, THAP40, THAP41, THAP42, THAP43, THAP44, THAP45, THAP46, THAP47, THAP48, THAP49, THAP50, THAP51, THAP52, THAP53, THAP54, THAP55, THAP56, THAP57, THAP58, THAP59, THAP60, THAP61, THAP62
```

- Graph holds **6** facts; model stated **62**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): THAP1, THAP2, THAP3, THAP4, THAP5, THAP6, THAP7, THAP8, THAP9, THAP10, THAP11, THAP12, THAP13, THAP14, THAP15
- Missed: CYP4B1, SLC19A2, SLC22A1, SLC22A2, SLC22A5, TPK1

### Alosetron — binds (`Compound::DB00969`, `CbG`)

**Question:** List every gene that the compound Alosetron binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ALOX12B, ALOX5, ALOX12P
```

- Graph holds **5** facts; model stated **3**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ALOX12B, ALOX5, ALOX12P
- Missed: CYP1A2, CYP2C9, CYP2E1, CYP3A4, HTR3A

### Sulfasalazine — binds (`Compound::DB00795`, `CbG`)

**Question:** List every gene that the compound Sulfasalazine binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
SUL1, TXNIP
```

- Graph holds **15** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): SUL1, TXNIP
- Missed: ABCC2, ABCG2, ACAT1, ALOX5, CHUK, CYP3A5, IKBKB, PLA2G1B, PPARG, PTGS1, PTGS2, SLC46A1, SLC7A11, SLCO1B1, TBXAS1

### Gabapentin — downregulates (`Compound::DB00996`, `CdG`)

**Question:** List every gene that the compound Gabapentin downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
GNAS, SCN9A, KCNJ11
```

- Graph holds **7** facts; model stated **3**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): GNAS, SCN9A, KCNJ11
- Missed: ACAT2, CCNB2, GDF15, IFRD2, TES, TIMM9, TNIP1

### Prazepam — binds (`Compound::DB01588`, `CbG`)

**Question:** List every gene that the compound Prazepam binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
Prazepam is not a known drug and does not have any genes associated with it. It's possible you might be referring to another medication or substance. Could you please provide more context or confirm if this was meant as an example of how to answer such a question? If so, I'd be happy to help identify relevant genes for other compounds.
```

- Graph holds **17** facts; model stated **0**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): (none)
- Missed: CYP3A4, GABRA1, GABRA2, GABRA3, GABRA5, GABRB1, GABRB2, GABRB3, GABRD, GABRE, GABRG1, GABRG2, GABRG3, GABRP, GABRR1, GABRR2, GABRR3

### Thalidomide — downregulates (`Compound::DB01041`, `CdG`)

**Question:** List every gene that the compound Thalidomide downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
THAL, DHCR7, ABCB11, CYP2C9, CYP3A4, CYP3A5, CYP3A7, CYP2D6, CYP2E1, CYP2C8, CYP2C19, CYP2C10, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, CYP2C19, C
```

- Graph holds **11** facts; model stated **46**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): THAL, DHCR7, ABCB11, CYP2C9, CYP3A4, CYP3A5, CYP3A7, CYP2D6, CYP2E1, CYP2C8, CYP2C19, CYP2C10, CYP2C19, CYP2C19, CYP2C19
- Missed: AMIGO2, ARL4C, ARNT2, DNAJA3, GRB7, IER3, NIT1, RAI14, TIMP1, TRIB3, ZNF395

### Prednisolone — downregulates (`Compound::DB00860`, `CdG`)

**Question:** List every gene that the compound Prednisolone downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
NR3C1, NR3C2
```

- Graph holds **8** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): NR3C1, NR3C2
- Missed: ADI1, CDKN1B, FHL2, IER3, IGFBP3, KIF14, PAN2, RPS4Y1

### Clobetasol propionate — downregulates (`Compound::DB01013`, `CdG`)

**Question:** List every gene that the compound Clobetasol propionate downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ABCA12, ADAMTS5, ANGPTL4, BCL2L6, CDH13, COL7A1, DUSP9, EPHB2, FBN1, GDF10, HSD17B1, ITGB8, KRT14, LAMB3, MIR138-5p, MYO1D, NRP1, PDE4C, PTCH1, RHOBTB4, SLC25A38, TCF7L2, VEGFA, WNT5A
```

- Graph holds **30** facts; model stated **24**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ABCA12, ADAMTS5, ANGPTL4, BCL2L6, CDH13, COL7A1, DUSP9, EPHB2, FBN1, GDF10, HSD17B1, ITGB8, KRT14, LAMB3, MIR138-5p
- Missed: ARL4C, CCL2, CDC20, CDC25B, CDC45, CDK4, CEBPA, COTL1, DDX10, DRAP1, DTL, DUSP4, FHL2, FOSL1, GDF15, IER3, IGFBP3, KIF2C, LBR, LIG1, PCNA, PNP, PRSS23, RAP1GAP, RELB …

### Ursodeoxycholic acid — downregulates (`Compound::DB01586`, `CdG`)

**Question:** List every gene that the compound Ursodeoxycholic acid downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ABCA12, ABCG8, ABCG5, ABCB4, ATP7A, CYP7A1, FAM3C, HSD17B10, LRP6, MDRP1, NURF, OPRM1, PAX2, SLC22A1, TSPAN9, UCP2, VPS35
```

- Graph holds **5** facts; model stated **17**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ABCA12, ABCG8, ABCG5, ABCB4, ATP7A, CYP7A1, FAM3C, HSD17B10, LRP6, MDRP1, NURF, OPRM1, PAX2, SLC22A1, TSPAN9
- Missed: NIT1, PAPD7, SHB, TRIB3, ZNF395

### Biperiden — binds (`Compound::DB00810`, `CbG`)

**Question:** List every gene that the compound Biperiden binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
BDNF, CREB1, DRD2, GRIK3, GRM4, GRM5, GRM6, GRM7, GRM8, GRM9, GRM10, GRM11, GRM12, GRM13, GRM14, GRM15, GRM16, GRM17, GRM18, GRM19, GRM20, GRM21, GRM22, GRM23, GRM24, GRM25, GRM26, GRM27, GRM28, GRM29, GRM30, GRM31, GRM32, GRM33, GRM34, GRM35, GRM36, GRM37, GRM38, GRM39, GRM40, GRM41, GRM42, GRM43, GRM44, GRM45, GRM46, GRM47, GRM48, GRM49, GRM50, GRM51, GRM52, GRM53, GRM54, GRM55, GRM56, GRM57, GRM58, GRM59, GRM60, GRM61,
```

- Graph holds **5** facts; model stated **62**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): BDNF, CREB1, DRD2, GRIK3, GRM4, GRM5, GRM6, GRM7, GRM8, GRM9, GRM10, GRM11, GRM12, GRM13, GRM14
- Missed: ABCB1, CHRM1, CHRM2, CHRNA2, CYP2D6

### Tioconazole — binds (`Compound::DB01007`, `CbG`)

**Question:** List every gene that the compound Tioconazole binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TPMT
```

- Graph holds **9** facts; model stated **1**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): TPMT
- Missed: CYP17A1, CYP19A1, CYP1A2, CYP2C19, CYP2C8, CYP2C9, CYP2E1, CYP3A4, CYP51A1

### Trifluoperazine — upregulates (`Compound::DB00831`, `CuG`)

**Question:** List every gene that the compound Trifluoperazine upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TRAF3IP2, TRIM19
```

- Graph holds **44** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): TRAF3IP2, TRIM19
- Missed: AARS, ABHD4, ACAT2, ACLY, ADAM10, AGR2, ALDOC, ANKRD10, C2CD2, CDK19, CDK7, CLPX, CYP51A1, DDIT4, DHCR24, DHCR7, ERBB3, FADS1, FDFT1, FDPS, FOXO4, GLRX, HLA-DMA, HMGCR, HMGCS1 …

### Spermine — binds (`Compound::DB00127`, `CbG`)

**Question:** List every gene that the compound Spermine binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
SMPK1, SMURF2, RNF43
```

- Graph holds **14** facts; model stated **3**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): SMPK1, SMURF2, RNF43
- Missed: CA14, CA4, CA5A, CA5B, CA6, CA7, ODC1, SAT1, SAT2, SLC22A1, SLC22A4, SMOX, SMS, XDH

### Flurbiprofen — binds (`Compound::DB00712`, `CbG`)

**Question:** List every gene that the compound Flurbiprofen binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
FLNB, FLNA
```

- Graph holds **11** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): FLNB, FLNA
- Missed: ABCC4, ALB, CYP2C9, PTGS1, PTGS2, SLC22A6, UGT1A1, UGT1A3, UGT1A9, UGT2B4, UGT2B7

### Indacaterol — binds (`Compound::DB05039`, `CbG`)

**Question:** List every gene that the compound Indacaterol binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ACO2, ACOT10, ACOT3, ACOT4, ACOT5, ACOT6, ACOT7, ACOT8, ACOT9, ACOT11, ACOT12, ACOT13, ACOT14, ACOT15, ACOT16, ACOT17, ACOT18, ACOT19, ACOT20, ACOT21, ACOT22, ACOT23, ACOT24, ACOT25, ACOT26, ACOT27, ACOT28, ACOT29, ACOT30, ACOT31, ACOT32, ACOT33, ACOT34, ACOT35, ACOT36, ACOT37, ACOT38, ACOT39, ACOT40, ACOT41, ACOT42, ACOT43, ACOT44, ACOT45, ACOT46, ACOT47, ACOT48, ACOT49, ACOT50, ACOT51, ACOT52, ACOT53, ACOT54, ACOT55, ACOT56, ACOT57, ACOT58, ACOT59, ACOT60, ACOT61, ACOT62, ACOT6
```

- Graph holds **5** facts; model stated **62**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ACO2, ACOT10, ACOT3, ACOT4, ACOT5, ACOT6, ACOT7, ACOT8, ACOT9, ACOT11, ACOT12, ACOT13, ACOT14, ACOT15, ACOT16
- Missed: ABCB1, ADRB1, ADRB2, CYP3A4, UGT1A1

### Pentobarbital — downregulates (`Compound::DB00312`, `CdG`)

**Question:** List every gene that the compound Pentobarbital downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
PENK, PRNP
```

- Graph holds **12** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): PENK, PRNP
- Missed: BRCA1, CDK4, EBNA1BP2, FABP5, GDF15, GSTZ1, PCM1, PSMB8, STAMBP, TSKU, TSPAN3, TXLNA

### Flurazepam — binds (`Compound::DB00690`, `CbG`)

**Question:** List every gene that the compound Flurazepam binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
GABAA_R1_BRAVINAK
```

- Graph holds **24** facts; model stated **1**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): GABAA_R1_BRAVINAK
- Missed: ABCB1, CYP2A6, CYP2E1, CYP3A4, GABRA1, GABRA2, GABRA3, GABRA4, GABRA5, GABRA6, GABRB1, GABRB2, GABRB3, GABRD, GABRE, GABRG1, GABRG2, GABRG3, GABRP, GABRQ, GABRR1, GABRR2, GABRR3, SLC22A2

### spinal cancer — associates (`Disease::DOID:5612`, `DaG`)

**Question:** List every gene associated with the disease spinal cancer. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TP53, RB1, SMAD4, PTEN, NF1, CDKN2A, CCND1, TP63, KRAS, BCL2, BRCA1, BRCA2
```

- Graph holds **7** facts; model stated **12**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): TP53, RB1, SMAD4, PTEN, NF1, CDKN2A, CCND1, TP63, KRAS, BCL2, BRCA1, BRCA2
- Missed: CNST, CYP4F22, MRI1, NF2, NRXN2, RBM10, SMARCE1

### Nefazodone — binds (`Compound::DB01149`, `CbG`)

**Question:** List every gene that the compound Nefazodone binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
NEUR1, CYP2D6
```

- Graph holds **15** facts; model stated **2**; **1** were correct.
- Coverage **6.7%**, precision **50.0%**
- Correct: CYP2D6
- Invented (not in graph): NEUR1
- Missed: ABCB1, ADRA1A, ADRA1B, ADRA2A, CYP3A4, CYP3A5, CYP3A7, CYP3A7-CYP3A51P, HTR1A, HTR2A, HTR2C, SLC6A2, SLC6A3, SLC6A4

### Olsalazine — binds (`Compound::DB01250`, `CbG`)

**Question:** List every gene that the compound Olsalazine binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ABCC8, ABCG2, ATP5A1, ATP7B, CYP3A4, CYP3A5, CYP3A7, CYP3A9, CYP3A10, CYP3A11, CYP3A12, CYP3A13, CYP3A14, CYP3A15, CYP3A16, CYP3A17, CYP3A18, CYP3A19, CYP3A20, CYP3A21, CYP3A22, CYP3A23, CYP3A24, CYP3A25, CYP3A26, CYP3A27, CYP3A28, CYP3A29, CYP3A30, CYP3A31, CYP3A32, CYP3A33, CYP3A34, CYP3A35, CYP3A36, CYP3A37, CYP3A38, CYP3A39, CYP3A40, CYP3A41, CYP3A42, CYP3A43, CYP3A44, CYP3A45, CYP3A46,
```

- Graph holds **6** facts; model stated **45**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ABCC8, ABCG2, ATP5A1, ATP7B, CYP3A4, CYP3A5, CYP3A7, CYP3A9, CYP3A10, CYP3A11, CYP3A12, CYP3A13, CYP3A14, CYP3A15, CYP3A16
- Missed: ALOX5, IFNG, PPARG, PTGS1, PTGS2, TPMT

### Furosemide — binds (`Compound::DB00695`, `CbG`)

**Question:** List every gene that the compound Furosemide binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ABCC9, ABCC5
```

- Graph holds **19** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ABCC9, ABCC5
- Missed: ABCC2, ALB, CA1, CA12, CA14, CA2, CA4, CA5A, CA5B, CA6, CA7, CA9, PGD, SLC12A1, SLC22A11, SLC22A5, SLC22A6, SLC22A8, SLCO2A1

### Scopolamine — binds (`Compound::DB00747`, `CbG`)

**Question:** List every gene that the compound Scopolamine binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
SCNR1, SCN4A
```

- Graph holds **7** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): SCNR1, SCN4A
- Missed: ABCB1, CHRM1, CHRM2, CHRM3, CHRM4, CHRM5, SI

### Desoximetasone — upregulates (`Compound::DB00547`, `CuG`)

**Question:** List every gene that the compound Desoximetasone upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
NCOT, CYP2C9, CYP3A4, CYP1B1, CYP2D6, CYP2C8, CYP2C19, CYP2C10, CYP2C9_2D6, CYP2C19_2D6, CYP2C19_2D6_2, CYP2C19_2D6_3, CYP2C19_2D6_4, CYP2C19_2D6_5, CYP2C19_2D6_6, CYP2C19_2D6_7, CYP2C19_2D6_8, CYP2C19_2D6_9, CYP2C19_2D6_10, CYP2C19_2D6_11, CYP2C19_2D6_12, CYP2C19_2D6_13, CYP2C19_2D6_14, CYP2C19_2D6_15, CYP2C19_2D6_16, CYP2C19_2D6_17, CYP2C19_2D6_18, CYP
```

- Graph holds **32** facts; model stated **28**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): NCOT, CYP2C9, CYP3A4, CYP1B1, CYP2D6, CYP2C8, CYP2C19, CYP2C10, CYP2C9_2D6, CYP2C19_2D6, CYP2C19_2D6_2, CYP2C19_2D6_3, CYP2C19_2D6_4, CYP2C19_2D6_5, CYP2C19_2D6_6
- Missed: ADCK3, AGL, ARID5B, CDK19, CEBPD, CES1, CNPY3, DDIT4, DNAJC15, FAIM, FKBP5, HSPB1, JADE2, MAL, MAPKAPK5, MUC1, NARFL, NFIL3, NFKBIA, PDK4, PER1, PRKAG2, PRKCD, PRKCH, PTK2B …

### Ketoprofen — binds (`Compound::DB01009`, `CbG`)

**Question:** List every gene that the compound Ketoprofen binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
PTGS2, COX1, COX2
```

- Graph holds **13** facts; model stated **3**; **1** were correct.
- Coverage **7.7%**, precision **33.3%**
- Correct: PTGS2
- Invented (not in graph): COX1, COX2
- Missed: ABCC4, ALB, CXCL8, CXCR1, CYP2C8, CYP2C9, PTGS1, SLC22A11, SLC22A6, SLC22A7, SLC22A8, SLCO1A2

### Ropivacaine — downregulates (`Compound::DB00296`, `CdG`)

**Question:** List every gene that the compound Ropivacaine downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
KCNJ11, KCNH2, SCN4A, SCN5A
```

- Graph holds **28** facts; model stated **4**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): KCNJ11, KCNH2, SCN4A, SCN5A
- Missed: ARGLU1, ATG3, BAG3, CD320, CDKN1B, CYB561, DCK, DDX10, DERA, EEF1A2, FABP5, FASTKD5, GRWD1, HOXA5, IFRD2, KRT8, LSR, MBOAT7, NSDHL, OXA1L, PCCB, PRR7, PTK2, S100A6, TIMM17B …

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

### Etoricoxib — upregulates (`Compound::DB01628`, `CuG`)

**Question:** List every gene that the compound Etoricoxib upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
EP300, PDE10A, PTEN, TNFRSF14
```

- Graph holds **12** facts; model stated **4**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): EP300, PDE10A, PTEN, TNFRSF14
- Missed: ICAM1, IKBKB, INPP1, KIT, LSM6, MALT1, PROS1, PTGS2, SLC1A4, SLC25A13, TATDN2, WIF1

### Escitalopram — downregulates (`Compound::DB01175`, `CdG`)

**Question:** List every gene that the compound Escitalopram downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
HTR2A, HTR2C
```

- Graph holds **8** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): HTR2A, HTR2C
- Missed: BACE2, COTL1, OXA1L, RNH1, RRP12, SCAND1, TSPAN4, VAT1

### Promazine — upregulates (`Compound::DB00420`, `CuG`)

**Question:** List every gene that the compound Promazine upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
MMP13, MMP2, MMP9, CCL5, CXCR4, IL6, TNF, VEGFA, PDGFB, FGF2, HSP70
```

- Graph holds **10** facts; model stated **11**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): MMP13, MMP2, MMP9, CCL5, CXCR4, IL6, TNF, VEGFA, PDGFB, FGF2, HSP70
- Missed: ACAT2, ALDOC, DDIT4, EBP, FDFT1, FOXO4, HMGCR, INSIG1, MSMO1, TSC22D3

### Sparfloxacin — downregulates (`Compound::DB01208`, `CdG`)

**Question:** List every gene that the compound Sparfloxacin downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
Sparfloxacin is an antibiotic that targets several bacterial genes involved in DNA replication and repair processes. Here are some of the key genes it has been shown to downregulate:

- dnaB (DNA polymerase III large subunit)
- dnaC (DNA gyrase A)
- dnaG (topoisomerase IV)
- recA (recognition protein for double-stranded breaks)
- uvrD (UvrABC photolyase)

These genes play crucial roles in bacterial cell survival and reproduction under stress conditions. Sparfloxacin works by inhibiting these enzymes, thereby disrupting essential cellular functions necessary for bacterial growth.
```

- Graph holds **11** facts; model stated **5**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): dnaB, dnaC, dnaG, recA, uvrD
- Missed: CDC20, COG7, IARS2, JMJD6, PHKA1, PKIG, SDC1, SPRED2, STUB1, TCEA2, VPS28

### Tolbutamide — downregulates (`Compound::DB01124`, `CdG`)

**Question:** List every gene that the compound Tolbutamide downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ACACA, ACADVL, ADH1B, APOC3, B4GALT7, CYP2E1, DPP4, FTO, GCKR, HNF4A, KCNJ5, LPL, MBD4, PPARA, PPARG, PRKAG2, SLC2A2, TCF7L2, UGT2B15, VDR, WFS1
```

- Graph holds **6** facts; model stated **21**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ACACA, ACADVL, ADH1B, APOC3, B4GALT7, CYP2E1, DPP4, FTO, GCKR, HNF4A, KCNJ5, LPL, MBD4, PPARA, PPARG
- Missed: ATP6V0B, CCDC86, IFRD2, PSMD2, RPN1, SPRED2

### Bupropion — downregulates (`Compound::DB01156`, `CdG`)

**Question:** List every gene that the compound Bupropion downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
SRD5A1, CYP2B6, COMT, MAO-A, MAOA, COMT, MAOB, MAOA, COMT, MAOC, MAOA, COMT, MAOD, MAOA, COMT, MAOE, MAOA, COMT, MAOF, MAOA, COMT, MAOG, MAOA, COMT, MAOH, MAOA, COMT, MAOK, MAOA, COMT, MAOL, MAOA, COMT, MAOM, MAOA, COMT, MAON, MAOA, COMT, MAOP, MAOA, COMT, MAOR, MAOA, COMT, MAOS, MAOA, COMT, MAOT, MAOA, COMT, MAOU, MAOA, COMT, MAOV, MAOA, COMT, MAOW, MAOA, COMT, MAOX, MAOA, COMT, MAOY, MAOA, COMT, MAOZ, MAOA, COMT, MAPE, MAOA, COMT, MAQ, MAOA, COMT, MAR, MAOA, COMT, MARS, MAOA, COMT, MARY, MAOA, COMT, MAST, MAOA, COMT, MAT, MAOA, COMT, MBP, MAOA, COMT, MCAD, MAOA, COMT, MDH2, MA
```

- Graph holds **26** facts; model stated **98**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): SRD5A1, CYP2B6, COMT, MAO-A, MAOA, COMT, MAOB, MAOA, COMT, MAOC, MAOA, COMT, MAOD, MAOA, COMT
- Missed: ABCF3, ADI1, ATP6V0B, ATP6V1D, CRYZ, DLD, GNAS, HDAC6, KIF2C, LDHB, MRPL19, MTHFD2, MYC, NNT, OXA1L, OXSR1, PSMG1, RPS4Y1, RRP1B, SDHB, SLC25A4, SLC35F2, STXBP1, TXNDC9, USP22 …

### Nisoldipine — upregulates (`Compound::DB00401`, `CuG`)

**Question:** List every gene that the compound Nisoldipine upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
NIS, HCN2
```

- Graph holds **9** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): NIS, HCN2
- Missed: CCDC92, DDIT4, HMOX1, PCK2, PLSCR1, PROS1, TRAPPC6A, WIF1, XBP1

### pharynx cancer — associates (`Disease::DOID:0060119`, `DaG`)

**Question:** List every gene associated with the disease pharynx cancer. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TP53, RB1, SMAD4, PTEN, CDKN2A, KRAS, TP63, NF1, APC, PIK3CA, STK11, SMARCB1, NOTCH1, MYC, BRCA2, TP73, TERT, KIT, EGFR, IDH1, IDH2, MET, AURKA, BAP1
```

- Graph holds **16** facts; model stated **24**; **2** were correct.
- Coverage **12.5%**, precision **8.3%**
- Correct: TP53, EGFR
- Invented (not in graph): RB1, SMAD4, PTEN, CDKN2A, KRAS, TP63, NF1, APC, PIK3CA, STK11, SMARCB1, NOTCH1, MYC, BRCA2, TP73
- Missed: ADH1B, ADH7, B4GALT5, BPIFA1, CCND1, CD6, CD79A, CDH1, CFAP45, CNDP2, EIF2AK1, MMP8, PDLIM7, TMEM8B

### Zolmitriptan — downregulates (`Compound::DB00315`, `CdG`)

**Question:** List every gene that the compound Zolmitriptan downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TCF7L2, TNFAIP3, IL1B, IL6, IL8, CXCL5, CCR4, CCR5, CCR6, CCR7, CCR9, CCR10, CCR11, CCR12, CCR13, CCR14, CCR15, CCR16, CCR17, CCR18, CCR19, CCR20, CCR21, CCR22, CCR23, CCR24, CCR25, CCR26, CCR27, CCR28, CCR29, CCR30, CCR31, CCR32, CCR33, CCR34, CCR35, CCR36, CCR37, CCR38, CCR39, CCR40, CCR41, CCR42, CCR43, CCR44, CCR45, CCR46, CCR47, CCR48, CCR49, CCR50, CCR51, CCR52, CCR53, CCR54, CCR55, CCR56, CCR57, CCR58, CCR59, CCR60,
```

- Graph holds **6** facts; model stated **62**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): TCF7L2, TNFAIP3, IL1B, IL6, IL8, CXCL5, CCR4, CCR5, CCR6, CCR7, CCR9, CCR10, CCR11, CCR12, CCR13
- Missed: CCDC86, CHMP4A, HAT1, NT5DC2, RPS4Y1, ZNF589

### abdominal aortic aneurysm — associates (`Disease::DOID:7693`, `DaG`)

**Question:** List every gene associated with the disease abdominal aortic aneurysm. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ABCA3, ADAMTS10, ANGPTL4, CLEC2D, FBN1, GDF5, HSPB8, ITGB6, KRT7, LRP1, MIR196A-5P, MMP2, MMP9, NID1, PTPN11, TGFBR2, VEGFC
```

- Graph holds **24** facts; model stated **17**; **3** were correct.
- Coverage **12.5%**, precision **17.6%**
- Correct: LRP1, MMP2, MMP9
- Invented (not in graph): ABCA3, ADAMTS10, ANGPTL4, CLEC2D, FBN1, GDF5, HSPB8, ITGB6, KRT7, MIR196A-5P, NID1, PTPN11, TGFBR2, VEGFC
- Missed: AAAS, AGT, AGTR1, APOE, CCL2, CDKN2A, DAB2IP, ELN, LDLR, LOX, MMP14, MMP3, NCF1, NFKB1, NOS2, P2RY12, PTGS2, SELL, SERPINE1, SOD2, TIMP4

### Aminolevulinic acid — upregulates (`Compound::DB00855`, `CuG`)

**Question:** List every gene that the compound Aminolevulinic acid upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ALAS2, ALAS3, UROS
```

- Graph holds **16** facts; model stated **3**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ALAS2, ALAS3, UROS
- Missed: CEBPD, CYTH1, DDIT4, EDEM1, HMOX1, HOMER2, INPP1, LGMN, LRRC16A, NFKBIA, NUCB2, POLD4, SPAG4, SPDEF, TIPARP, YTHDF1

### Carbidopa — upregulates (`Compound::DB00190`, `CuG`)

**Question:** List every gene that the compound Carbidopa upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
dacb1
```

- Graph holds **6** facts; model stated **1**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): dacb1
- Missed: EPCAM, PAK1, PIK3CA, PRKCQ, SSBP2, TRAPPC6A

### Hexetidine — downregulates (`Compound::DB08958`, `CdG`)

**Question:** List every gene that the compound Hexetidine downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
HEPZ1, HEPZ2
```

- Graph holds **11** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): HEPZ1, HEPZ2
- Missed: ATP6V1D, CDC25B, DLD, FBXO21, JMJD6, MRPS16, PDHX, TIMM9, TNIP1, VIM, ZW10

### Levothyroxine — downregulates (`Compound::DB00451`, `CdG`)

**Question:** List every gene that the compound Levothyroxine downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TSHR, TRAB, TRB1, TRB2, TRB3, TRB4, TRB5, TRB6, TRB7, TRB8, TRB9, TRB10, TRB11, TRB12, TRB13, TRB14, TRB15, TRB16, TRB17, TRB18, TRB19, TRB20, TRB21, TRB22, TRB23, TRB24, TRB25, TRB26, TRB27, TRB28, TRB29, TRB30, TRB31, TRB32, TRB33, TRB34, TRB35, TRB36, TRB37, TRB38, TRB39, TRB40, TRB41, TRB42, TRB43, TRB44, TRB45, TRB46, TRB47, TRB48, TRB49, TRB50, TRB51, TRB52, TRB53, TRB54, TRB55, TRB56, TRB57, TRB58, TRB59, TRB60, TRB
```

- Graph holds **8** facts; model stated **63**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): TSHR, TRAB, TRB1, TRB2, TRB3, TRB4, TRB5, TRB6, TRB7, TRB8, TRB9, TRB10, TRB11, TRB12, TRB13
- Missed: ATP6V1D, CDC20, FHL2, GTPBP8, HSPD1, NPDC1, PPP2R5E, RPS4Y1

### Nicardipine — upregulates (`Compound::DB00622`, `CuG`)

**Question:** List every gene that the compound Nicardipine upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
NOX2, NOS3
```

- Graph holds **5** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): NOX2, NOS3
- Missed: CCP110, LAMA3, ME2, NNT, SELL

### Metrizamide — upregulates (`Compound::DB01578`, `CuG`)

**Question:** List every gene that the compound Metrizamide upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ACO2, CYP1A1, CYP1B1, CYP2C9, CYP2E1, GSTM1, NQO1
```

- Graph holds **5** facts; model stated **7**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ACO2, CYP1A1, CYP1B1, CYP2C9, CYP2E1, GSTM1, NQO1
- Missed: NPR3, PEX11A, PRKCQ, RPL39L, TMEM110

### Amcinonide — downregulates (`Compound::DB00288`, `CdG`)

**Question:** List every gene that the compound Amcinonide downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
AMCN, CYP2C19, CYP3A4, CYP3A5, CYP3A7, CYP3A8, CYP3A9, CYP3A10, CYP3A11, CYP3A12, CYP3A13, CYP3A14, CYP3A15, CYP3A16, CYP3A17, CYP3A18, CYP3A19, CYP3A20, CYP3A21, CYP3A22, CYP3A23, CYP3A24, CYP3A25, CYP3A26, CYP3A27, CYP3A28, CYP3A29, CYP3A30, CYP3A31, CYP3A32, CYP3A33, CYP3A34, CYP3A35, CYP3A36, CYP3A37, CYP3A38, CYP3A39, CYP3A40, CYP3A41, CYP3A42, CYP3A43, CYP3A44, CYP3A45, CYP3A46, C
```

- Graph holds **11** facts; model stated **45**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): AMCN, CYP2C19, CYP3A4, CYP3A5, CYP3A7, CYP3A8, CYP3A9, CYP3A10, CYP3A11, CYP3A12, CYP3A13, CYP3A14, CYP3A15, CYP3A16, CYP3A17
- Missed: ACAT2, ADGRG1, ARL4C, CCL2, DFFA, DKK3, DNMT3A, HAT1, IER3, IGFBP3, PTPRK

### Sitagliptin — downregulates (`Compound::DB01261`, `CdG`)

**Question:** List every gene that the compound Sitagliptin downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ABCC8, ATP2B1, CYP3A4, CYP3A5, CYP3A7, CYP3A9, CYP3A10, CYP3A11, CYP3A12, CYP3A13, CYP3A14, CYP3A15, CYP3A16, CYP3A17, CYP3A18, CYP3A19, CYP3A20, CYP3A21, CYP3A22, CYP3A23, CYP3A24, CYP3A25, CYP3A26, CYP3A27, CYP3A28, CYP3A29, CYP3A30, CYP3A31, CYP3A32, CYP3A33, CYP3A34, CYP3A35, CYP3A36, CYP3A37, CYP3A38, CYP3A39, CYP3A40, CYP3A41, CYP3A42, CYP3A43, CYP3A44, CYP3A45, CYP3A46, CYP3A47, C
```

- Graph holds **44** facts; model stated **45**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ABCC8, ATP2B1, CYP3A4, CYP3A5, CYP3A7, CYP3A9, CYP3A10, CYP3A11, CYP3A12, CYP3A13, CYP3A14, CYP3A15, CYP3A16, CYP3A17, CYP3A18
- Missed: ALAS1, APBB2, ATP11B, AURKB, BAX, BPHL, CD40, CHAC1, CORO1A, CRELD2, CTGF, CTNND1, CTSD, DFFA, DKK3, EDN1, EXT1, FRS2, IFNAR1, IL4R, ITFG1, KIAA0196, MEST, MRPL13, NVL …

### Fluconazole — downregulates (`Compound::DB00196`, `CdG`)

**Question:** List every gene that the compound Fluconazole downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ABCC1, ABCG2, CYP3A4, CYP3A5, CYP3A7, CYP4F2, CYP4F6, CYP4F8, CYP4V2, FANCA, GJB2, HLA-A, HLA-B, HLA-C, HLA-E, HLA-F, HLA-G, HSPA9, LPL, MUC1, NUDT1, PAX2, SLC2A1, TUBB3, UGT2B15, VDR
```

- Graph holds **10** facts; model stated **26**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ABCC1, ABCG2, CYP3A4, CYP3A5, CYP3A7, CYP4F2, CYP4F6, CYP4F8, CYP4V2, FANCA, GJB2, HLA-A, HLA-B, HLA-C, HLA-E
- Missed: ABCF3, ARFIP2, BAG3, CASC3, DNTTIP2, EPB41L2, HOXA5, PIGB, USP22, WFS1

### Memantine — upregulates (`Compound::DB01043`, `CuG`)

**Question:** List every gene that the compound Memantine upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
DLG1, DISC1, GRIN2A, GRIN2B, GRIN2C, GRIN2D, GRIN3A, GRIN3B, GRIN4, MAPK8, MAPK9, MAPK10, NRG1, NRGN, PLCB1, PLCB2, PLCB3, PLCB4, PLCB5, PLCB6, PLCB7, PLCBD1, PLCBD2, PLCBD3, PLCBD4, PLCBD5, PLCBD6, PLCBD7, PLCBD8, PLCBD9, PLCBD10, PLCBD11, PLCBD12, PLCBD13, PLCBD14, PLCBD15, PLCBD16, PLCBD17, PLCBD18, PLCBD19, PLCBD20, PLCBD21, PLCBD22, PLCBD23, PLCBD24, PLCBD25, PLCBD26, PLCBD27, PLCBD28, PLCBD29, PLCBD30, PLCBD31, PLCBD32, PLCBD33, PLCBD34, PLCBD35, PLCBD36, PLCBD37, PLCBD38, PLCBD39, PLCBD40, PLCBD41, PLCBD42, PLCBD43, PLCBD44
```

- Graph holds **5** facts; model stated **65**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): DLG1, DISC1, GRIN2A, GRIN2B, GRIN2C, GRIN2D, GRIN3A, GRIN3B, GRIN4, MAPK8, MAPK9, MAPK10, NRG1, NRGN, PLCB1
- Missed: CASP7, CYTH1, NFKBIA, PRKCD, TIPARP

### Ketorolac — downregulates (`Compound::DB00465`, `CdG`)

**Question:** List every gene that the compound Ketorolac downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
COX2, COX3
```

- Graph holds **6** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): COX2, COX3
- Missed: CSRP1, DUSP4, IER3, NPDC1, RPS4Y1, UGDH

### Dextrothyroxine — upregulates (`Compound::DB00509`, `CuG`)

**Question:** List every gene that the compound Dextrothyroxine upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
CYP3A4, CYP2D6
```

- Graph holds **11** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): CYP3A4, CYP2D6
- Missed: AGR2, CDK6, CEBPA, CNPY3, FOXO4, GHR, GPATCH8, NCK1, PCK2, STXBP1, TATDN2

### Flecainide — upregulates (`Compound::DB01195`, `CuG`)

**Question:** List every gene that the compound Flecainide upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
KCNJ2, KCNH2, SCN5A
```

- Graph holds **8** facts; model stated **3**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): KCNJ2, KCNH2, SCN5A
- Missed: AARS, CDK6, DDIT4, EIF4EBP1, GARS, HMOX1, MTHFD2, PHGDH

### Donepezil — downregulates (`Compound::DB00843`, `CdG`)

**Question:** List every gene that the compound Donepezil downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ARSB, CYP2B6, COMT, MAOB, SLC38A1
```

- Graph holds **11** facts; model stated **5**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ARSB, CYP2B6, COMT, MAOB, SLC38A1
- Missed: ARL4C, CANT1, CCL2, CCNB2, CDC20, IER3, PARP2, RAP1GAP, TOR1A, TP53BP1, TUBB6

### Calcipotriol — upregulates (`Compound::DB02300`, `CuG`)

**Question:** List every gene that the compound Calcipotriol upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TCF7L2, RORA
```

- Graph holds **24** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): TCF7L2, RORA
- Missed: AARS, ADGRE5, ALDOC, BNIP3, CDKN1A, DDIT4, GADD45A, HERC6, HMOX1, IGFBP3, IL1B, INPP4B, MMP1, NET1, NFKBIA, NPC1, PCK2, PDGFA, PHGDH, POLD4, SQRDL, TCEA2, TXNRD1, ZFP36

### Nizatidine — upregulates (`Compound::DB00585`, `CuG`)

**Question:** List every gene that the compound Nizatidine upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
KCNJ11, KCNH2, SCN4A
```

- Graph holds **38** facts; model stated **3**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): KCNJ11, KCNH2, SCN4A
- Missed: ATP11B, BMP4, BUB1B, CASP10, COL11A1, CTNND1, CXCR4, DFFB, DNMT1, FGFR2, FSD1, FZD1, HBB, HIST2H2BE, HLA-DRA, HS2ST1, IFNAR1, IPO13, KRT6A, MAP7, NARFL, NCAPD2, NFKBIE, PAK1, PCK2 …

### Novobiocin — upregulates (`Compound::DB01051`, `CuG`)

**Question:** List every gene that the compound Novobiocin upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
NOX2, NOS3
```

- Graph holds **7** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): NOX2, NOS3
- Missed: BIRC2, E2F2, ERBB3, FOXO4, LPL, PTGS2, SUV39H1

### Reserpine — upregulates (`Compound::DB00206`, `CuG`)

**Question:** List every gene that the compound Reserpine upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
SERPINE1, SERPINB2, SERPINB3, SERPINB4, SERPINB5, SERPINB6, SERPINB7, SERPINB8, SERPINB9, SERPINB10, SERPINB11, SERPINB12, SERPINB13, SERPINB14, SERPINB15, SERPINB16, SERPINB17, SERPINB18, SERPINB19, SERPINB20, SERPINB21, SERPINB22, SERPINB23, SERPINB24, SERPINB25, SERPINB26, SERPINB27, SERPINB28, SERPINB29, SERPINB30, SERPINB31, SERPINB32, SERPINB33, SERPINB34, SERPINB35, SERPINB36, SERPINB37, SERPINB38, SERPINB39, SERPINB40, SERPINB41, SERPINB42, SERPINB43, SERPINB44, SERPINB45, SERPINB46, SERPINB47, SERPINB48, SERPINB49, SERPINB50, SERPINB51, SERPINB
```

- Graph holds **54** facts; model stated **52**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): SERPINE1, SERPINB2, SERPINB3, SERPINB4, SERPINB5, SERPINB6, SERPINB7, SERPINB8, SERPINB9, SERPINB10, SERPINB11, SERPINB12, SERPINB13, SERPINB14, SERPINB15
- Missed: AARS, ABCC5, ABHD4, ACLY, ALDOC, AMDHD2, BHLHE40, CDK19, CDK7, CPSF4, CTSL, DDIT4, DHCR7, EDEM1, FADS2, FOXO3, GSTA4, HDAC6, HLA-DMA, HMGCR, HMGCS1, HMOX1, INSIG1, KAT5, LRP10 …

### Penicillin V — upregulates (`Compound::DB00417`, `CuG`)

**Question:** List every gene that the compound Penicillin V upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
PENK
```

- Graph holds **6** facts; model stated **1**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): PENK
- Missed: CDK6, CTNNAL1, EPHB2, HSD17B11, SATB1, SUV39H1

### Salmeterol — upregulates (`Compound::DB00938`, `CuG`)

**Question:** List every gene that the compound Salmeterol upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
SALTRKB1A, SALTRKB2
```

- Graph holds **17** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): SALTRKB1A, SALTRKB2
- Missed: ABHD4, ACAT2, ALDOC, DDIT4, EBP, EDEM1, FDFT1, FDPS, HMGCR, HMGCS1, IDI1, INSIG1, LGMN, MSMO1, MVD, NSDHL, SCD

### Sulfamethizole — upregulates (`Compound::DB00576`, `CuG`)

**Question:** List every gene that the compound Sulfamethizole upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
SULT1A2, CYP3A4, CYP2C9, CYP2C19
```

- Graph holds **10** facts; model stated **4**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): SULT1A2, CYP3A4, CYP2C9, CYP2C19
- Missed: CDK5R1, CXCL2, GHR, NNT, PROS1, RAB27A, TATDN2, TRAPPC6A, WRB, XBP1

### Terazosin — upregulates (`Compound::DB01162`, `CuG`)

**Question:** List every gene that the compound Terazosin upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
AR, ERα, GR, HSD17B3, KDR, LPA, MEGF8, NOS2, PDE4DIE, PRKAG2, SLC2A9, TCF7L2
```

- Graph holds **7** facts; model stated **12**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): AR, ERα, GR, HSD17B3, KDR, LPA, MEGF8, NOS2, PDE4DIE, PRKAG2, SLC2A9, TCF7L2
- Missed: ABCC5, CASP2, CCP110, CES1, MSRA, RRS1, ZNF586

### Trichlormethiazide — upregulates (`Compound::DB01021`, `CuG`)

**Question:** List every gene that the compound Trichlormethiazide upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TRIM28
```

- Graph holds **7** facts; model stated **1**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): TRIM28
- Missed: CNOT4, GHR, HP, PEX11A, SERPINA3, TSEN2, WRB

### Calcitriol — upregulates (`Compound::DB00136`, `CuG`)

**Question:** List every gene that the compound Calcitriol upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
VDR
```

- Graph holds **38** facts; model stated **1**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): VDR
- Missed: ADGRE5, ALAS1, ARHGEF2, BCL2, BHLHE40, C2CD5, CCDC92, CCL22, CEBPA, CES1, CFLAR, CRIP1, CTSD, DDIT4, FOXO3, GADD45A, GLRX, IL4R, INPP1, LCN2, LPGAT1, MAL, MAPK13, MCOLN1, NFKBIA …

### adrenal gland cancer — associates (`Disease::DOID:3953`, `DaG`)

**Question:** List every gene associated with the disease adrenal gland cancer. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ADGRG1, ADH1B, ADCY8, ARL3, ARHGAP24, ATF6, BCL2L11, BRCA1, BRIP1, CDKN2A, CYP17A1, DDX5, EPHA9, FAM104A, GPR132, HLA-A, HLA-B, HLA-C, HLA-E, HLA-F, HLA-G, KMT2D, LRP1, MCM6, MYC, NFE2L2, NRAS, PDCD1LG2, PTEN, RASSF1A, SLC25A34, TCF7L2, TP53, UBE2I, VPS35, WDR11, XPA, YWHAZ
```

- Graph holds **38** facts; model stated **38**; **2** were correct.
- Coverage **5.3%**, precision **5.3%**
- Correct: CDKN2A, TP53
- Invented (not in graph): ADGRG1, ADH1B, ADCY8, ARL3, ARHGAP24, ATF6, BCL2L11, BRCA1, BRIP1, CYP17A1, DDX5, EPHA9, FAM104A, GPR132, HLA-A
- Missed: ABCB1, BAD, BRAF, CDC42, CTNNB1, DAXX, EGFR, GNAS, GNRH1, GNRHR, HSD17B11, IGF1R, IGF2, KCNJ5, MED12, MEN1, MRPL48, MYCN, NR5A1, POMC, PRKACA, PTGS2, RB1, REN, RRM1 …

### migraine — associates (`Disease::DOID:6364`, `DaG`)

**Question:** List every gene associated with the disease migraine. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
AADC,BHLHE4,CAMK2B,GNAS,GPR98,SLC1A3,TPM3
```

- Graph holds **46** facts; model stated **7**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): AADC, BHLHE4, CAMK2B, GNAS, GPR98, SLC1A3, TPM3
- Missed: ACE, AJAP1, ASTN2, ATP1A2, ATP1A3, BDNF, CACNA1A, CALCA, CALCRL, DGCR14, EDNRA, ESR1, FHL5, FOS, GOLPH3, HTR1A, HTR1B, HTR1D, HTR2A, HTR2B, HTR2C, HTR3A, HTR7, KCNK18, LRP1 …

### Kawasaki disease — associates (`Disease::DOID:13378`, `DaG`)

**Question:** List every gene associated with the disease Kawasaki disease. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
NOX2, TNFAIP3, IL1B, IFNG, STAT4, PTN, CCR5, CXCL8, FPR2, TLR4, LTA, CD68
```

- Graph holds **14** facts; model stated **12**; **1** were correct.
- Coverage **7.1%**, precision **8.3%**
- Correct: CCR5
- Invented (not in graph): NOX2, TNFAIP3, IL1B, IFNG, STAT4, PTN, CXCL8, FPR2, TLR4, LTA, CD68
- Missed: ADCK4, BLK, CA8, CD4, CD40, CENPU, CRP, FCGR2A, IL10, ITGAE, ITPKC, MMP9, VEGFA

### attention deficit hyperactivity disorder — associates (`Disease::DOID:1094`, `DaG`)

**Question:** List every gene associated with the disease attention deficit hyperactivity disorder. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ACSN1, ADH1B, ADCY8, ANK3, BDNF, CHRNA7, CNTNAP2, DAB1, DISC1, DRD4, EFNA5, FMRP, GAD1, GRM6, HTR2A, KCNJ2, KCTD10, LMX1A, MAPT, MEG3, NRG1, NRXN1, OPN1SW, PDE4DIP, PRDM16, RAI1, SCN1A, SCN9A, SLC6A4, TPH2, UBE3A, VPS13C, WDR45
```

- Graph holds **41** facts; model stated **33**; **6** were correct.
- Coverage **14.6%**, precision **18.2%**
- Correct: ANK3, BDNF, DRD4, HTR2A, SLC6A4, TPH2
- Invented (not in graph): ACSN1, ADH1B, ADCY8, CNTNAP2, DAB1, DISC1, EFNA5, FMRP, GAD1, GRM6, KCNJ2, KCTD10, LMX1A, MAPT, MEG3
- Missed: ADRA2A, ADRA2C, AS3MT, CACNA1C, CACNB2, CCDC68, CHRNA4, COMT, CSMD1, DPYD, DRD1, DRD2, DRD3, DRD5, EFS, EP300, GABRQ, GRM7, HRH3, HTR1B, IMPACT, ITIH3, MAOA, MB21D1, MMP16 …

### Creutzfeldt-Jakob disease — associates (`Disease::DOID:11949`, `DaG`)

**Question:** List every gene associated with the disease Creutzfeldt-Jakob disease. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
CDKL5, PRNP
```

- Graph holds **7** facts; model stated **2**; **1** were correct.
- Coverage **14.3%**, precision **50.0%**
- Correct: PRNP
- Invented (not in graph): CDKL5
- Missed: CTSD, HLA-DQB1, MTMR7, NPAS2, PRND, YWHAZ

### testicular cancer — associates (`Disease::DOID:2998`, `DaG`)

**Question:** List every gene associated with the disease testicular cancer. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TP53, RB1, PTEN, CDKN2A, BRCA1, BRCA2, TP63, STK11, SMAD4, PIK3CA, AKT1, ATM, CHEK2, BARD1, DCC, APC, NF1, PTCH1, KIT, NOTCH1, RAS, HRAS, NRAS, TP73, TSC1, TSC2, FGFR3, MET, EGFR, KRAS, BRAF, RAF1, PIK3R1, PIK3CD, PIK3CA, PIK3CB, PIK3R3, PIK3R4, PIK3R5, PIK3CG, PIK3C3, MAPK1, MAPK3, MAPK14, MAPK8, MAPK9, MAPK10, MAPK12, MAPK13, MAPK14, MAPK15, MAPK16, MAPK17, MAPK18, MAPK19, MAPK2, MAPK3, MAPK4, MAPK5, MAPK6, MAPK7, MAPK8, MAPK9, MAPK10, MAPK11, MAPK12, MAPK13, MAPK14, MAPK15, MAPK16, MAPK17
```

- Graph holds **23** facts; model stated **71**; **3** were correct.
- Coverage **13.0%**, precision **4.2%**
- Correct: STK11, KIT, FGFR3
- Invented (not in graph): TP53, RB1, PTEN, CDKN2A, BRCA1, BRCA2, TP63, SMAD4, PIK3CA, AKT1, ATM, CHEK2, BARD1, DCC, APC
- Missed: ATF7IP, BCL10, DAZL, DMRT1, DNMT3L, ERCC1, ERCC4, GGN, H2AFZ, HPGDS, INSL3, KITLG, MAD1L1, MMP2, PITX1, PRDM14, RFWD3, SLC2A6, STK10, TFAP2C

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

### vitiligo — associates (`Disease::DOID:12306`, `DaG`)

**Question:** List every gene associated with the disease vitiligo. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
VITM1, TYR, SLC45A2, CYP3A4, MC1R, OCA2, AGTR1, CDKN2B-AS1, PTCH1, LRRFIP2, RHOBTB7, PAX3, NRAS, MAP2K1, FOS, JUN, STAT3, TP63, KRT8, KRT10, KCNQ1, GNAI2, TNFRSF17, TRAF3, IRF1, IL17RA, IFNGR2, CXCL13, CCR9, FCGR3A, HLA-DQB1, HLA-DRB1, HLA-A, HLA-B, HLA-C, HLA-E, HLA-F, HLA-G, HLA-H, HLA-DRB3, HLA-DRB4, HLA-DRB5, HLA-DRB6, HLA-DRB7, HLA-DRB8, HLA-DRB9, HLA-DQA1, HLA-DQB1, HLA-DRB1, HLA-DRB2, HLA-DRB3, HLA-DRB4, HLA-DRB5, HLA-DRB6, HLA-DRB7, HLA-DRB8, HLA-
```

- Graph holds **38** facts; model stated **57**; **2** were correct.
- Coverage **5.3%**, precision **3.5%**
- Correct: TYR, MC1R
- Invented (not in graph): VITM1, SLC45A2, CYP3A4, OCA2, AGTR1, CDKN2B-AS1, PTCH1, LRRFIP2, RHOBTB7, PAX3, NRAS, MAP2K1, FOS, JUN, STAT3
- Missed: AIRE, BACH2, C12orf10, C1QTNF6, CASP7, CAT, CCR6, CD44, CD80, CD8A, CLNK, CTLA4, DCT, DDX6, FOXP1, GSTM1, GSTT1, GZMB, HERC2, IFIH1, IKZF4, IL2RA, LPP, LRR1, MITF …

### meningioma — associates (`Disease::DOID:3565`, `DaG`)

**Question:** List every gene associated with the disease meningioma. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TP53, PTEN, NF1, STK17B, CDKN2A, CCND1, KIT, EGFR, BRAF, NRAS, KRAS, TP63, SMARCA4, PIK3CA, MAP2K1, MAP2K2, RAF1, BCL2L11, NOTCH1, MYC, PDCD1, TERT, RB1, DCC, JAK2, FGFR3, MET, ABL1, AKT1, AKT2, AKT3, ERBB2, RHOBTB4, GNAQ, GNA11, PRKAG2, PPP2R1A, PPP2R1B, PPARG, SLC2A9, FGF8, FGF10, FGF19, FGF21, FGF23, VEGFA, VEGFB, VEGFC, VEGFD, VEGFE, VEGFF, VEGFG, VEGFH, VEGFI, VEGFK, VEGFL, VEGFM, VEGFN, VEGFO, VEGFP, VEGFS, VEGFT, VEGFU, VEGFY, VEGFZ, VEGFX, VEGFY, VEGFZ, VEGFX, VEGFY, VEGFZ, VEGFX
```

- Graph holds **28** facts; model stated **72**; **4** were correct.
- Coverage **14.3%**, precision **5.6%**
- Correct: TP53, PTEN, AKT1, ERBB2
- Invented (not in graph): NF1, STK17B, CDKN2A, CCND1, KIT, EGFR, BRAF, NRAS, KRAS, TP63, SMARCA4, PIK3CA, MAP2K1, MAP2K2, RAF1
- Missed: ALAD, AP1B1, CD34, CST3, CSTB, CTSL, EPB41L3, HES1, MLLT10, MN1, NAB2, NF2, PDGFB, PGR, PLAU, PLAUR, PRDM10, SMARCB1, SMARCE1, SMO, TMEM97, TRAF7, TSHB, TXNDC16

### ocular cancer — associates (`Disease::DOID:2174`, `DaG`)

**Question:** List every gene associated with the disease ocular cancer. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TP53, RB1, CDKN2A, PTEN, SMAD4, NF1, STK11/LKB1, PIK3CA, AKT1, BRCA2, TP63, TERT, MLH1, MSH2, DCC, NOTCH1, JAK2, STAT3, MYC, CCND1, KIT
```

- Graph holds **54** facts; model stated **21**; **5** were correct.
- Coverage **9.3%**, precision **23.8%**
- Correct: TP53, RB1, AKT1, MYC, CCND1
- Invented (not in graph): PTEN, SMAD4, NF1, STK11/LKB1, PIK3CA, BRCA2, TP63, TERT, MLH1, MSH2, DCC, NOTCH1, JAK2, STAT3, KIT
- Missed: AZU1, BAP1, CCND2, CCND3, CDC25A, CDK2, CDK4, CDK6, CDKN1A, CDKN1B, CDKN2B, CDKN2C, CRTC1, E2F1, E2F2, E2F3, E2F4, E2F5, EIF1AX, EP300, ESD, GNA11, GNAQ, H1F0, HDAC1 …

### gallbladder cancer — associates (`Disease::DOID:3121`, `DaG`)

**Question:** List every gene associated with the disease gallbladder cancer. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ABCA12, ABCB4, ABCD1, ABCG8, ADAMTS9, APOA5, ATP7C, BCL6, BRCA1, BRCA2, CDH1, CYP2E1, DDX3X, ESR1, FANCF, GATA3, HLA-A, HLA-B, HLA-C, HLA-E, HLA-F, HLA-G, KMT2D, LRP2, MGMT, MYC, NFE2L2, PAX8, PTEN, RASSF1A, SLC25A4, TERT, TP53, UBE2I, VPS35
```

- Graph holds **13** facts; model stated **35**; **1** were correct.
- Coverage **7.7%**, precision **2.9%**
- Correct: TP53
- Invented (not in graph): ABCA12, ABCB4, ABCD1, ABCG8, ADAMTS9, APOA5, ATP7C, BCL6, BRCA1, BRCA2, CDH1, CYP2E1, DDX3X, ESR1, FANCF
- Missed: BCL2, EGFR, ERBB2, ERBB3, ERBB4, HRAS, KEAP1, KRAS, NEK8, NRAS, PDPN, UCHL1

### dental caries — associates (`Disease::DOID:216`, `DaG`)

**Question:** List every gene associated with the disease dental caries. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ABCC11, ABCG2, ADH1B, ALDH2, AMACR, CYP1A1, CYP1A2, CYP26C1, DUSP9, FAM43B, GNAS, HSD17B1, KCNJ5, KCNJ10, LCT, MTHFR, NAGPA, NR5A1, OGG1, PAX8, PRSS1, SLC25A3, TSPAN10, UGT2B15, VDR, WNT5A
```

- Graph holds **13** facts; model stated **26**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ABCC11, ABCG2, ADH1B, ALDH2, AMACR, CYP1A1, CYP1A2, CYP26C1, DUSP9, FAM43B, GNAS, HSD17B1, KCNJ5, KCNJ10, LCT
- Missed: ANGPTL6, CD79A, CDIPT, CNOT8, CPQ, DEDD, DMTF1, INO80, IRF6, LTF, LYZL2, SMARCA2, SMARCA4

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

### focal segmental glomerulosclerosis — associates (`Disease::DOID:1312`, `DaG`)

**Question:** List every gene associated with the disease focal segmental glomerulosclerosis. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
Focal_segmental_glomerulosclerosis_GWAS, FSGS1, FSGS2, FSGS3, FSGS4, FSGS5, FSGS6, FSGS7, FSGS8, FSGS9, FSGS10
```

- Graph holds **44** facts; model stated **11**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): Focal_segmental_glomerulosclerosis_GWAS, FSGS1, FSGS2, FSGS3, FSGS4, FSGS5, FSGS6, FSGS7, FSGS8, FSGS9, FSGS10
- Missed: ACE, ACTA2, ACTN4, AGT, AGTR1, AGTR2, ALB, ANGPT2, APOL1, CD2AP, CD40LG, CD79A, COL4A1, COL4A3, COL4A4, CTGF, EDN1, FN1, GNAQ, HAVCR1, INF2, LIPC, LPL, MMP2, MMP9 …

### malignant mesothelioma — associates (`Disease::DOID:1790`, `DaG`)

**Question:** List every gene associated with the disease malignant mesothelioma. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
SMAD4, TP53, BAP1
```

- Graph holds **9** facts; model stated **3**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): SMAD4, TP53, BAP1
- Missed: CALB2, EPCAM, KRT5, MCAM, MSLN, NF2, PTGER4, THBD, WT1

### thoracic aortic aneurysm — associates (`Disease::DOID:14004`, `DaG`)

**Question:** List every gene associated with the disease thoracic aortic aneurysm. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
THBS1, TNFAIP3, TSPAN8, ITGB2, FBN1, COL4A5, COL4A6, MAP3K7, PTPN22, PTEN, SMAD9, MYH11, RAC1, VEGFC, CDKN2B-AS1
```

- Graph holds **13** facts; model stated **15**; **2** were correct.
- Coverage **15.4%**, precision **13.3%**
- Correct: FBN1, MYH11
- Invented (not in graph): THBS1, TNFAIP3, TSPAN8, ITGB2, COL4A5, COL4A6, MAP3K7, PTPN22, PTEN, SMAD9, RAC1, VEGFC, CDKN2B-AS1
- Missed: ACTA2, ADAM10, ADAM17, MMP2, MMP9, MYLK, PRKG1, SMAD3, TGFB2, TGFBR1, TGFBR2

### nephrolithiasis — associates (`Disease::DOID:585`, `DaG`)

**Question:** List every gene associated with the disease nephrolithiasis. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
NPHS1, NPHS2, KCNJ5, CYP4F2, FBN1, COL8A3, COL8A5, TNNI3, MYH11, TPM3, LRP1, PTPN22, CDKN2B-AS1, DUSP9, SLC26A3, ATP7B, CLCNKB, SCN1A, SCN2A, SCN3A, SCN4A, SCN5A, SCN8A, KCNE1, KCNH2, KCNE2, KCNE3, KCNA5, KCNB1, KCND2, KCNE4, KCNE5, KCNE6, KCNE7, KCNE8, KCNE9, KCNE10, KCNE11, KCNE12, KCNE13, KCNE14, KCNE15, KCNE16, KCNE17, KCNE18, KCNE19, KCNE20, KCNE21, KCNE22, KCNE23, KCNE24, KCNE25, KCNE26, KCNE27, KCNE28, KCNE29, KCNE30, KCNE31, KCNE32, KCNE33, KCNE34, KCNE35, KCNE36, KCNE37
```

- Graph holds **26** facts; model stated **64**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): NPHS1, NPHS2, KCNJ5, CYP4F2, FBN1, COL8A3, COL8A5, TNNI3, MYH11, TPM3, LRP1, PTPN22, CDKN2B-AS1, DUSP9, ATP7B
- Missed: ADCY10, AGXT, AMBP, APRT, AQP1, ATP6V0A4, CHRM3, CLCN4, CLCN5, CLDN14, CLDN16, DGKH, GRHPR, PFN3, PTH, RGS14, SLC22A12, SLC26A1, SLC26A6, SLC2A9, SLC34A1, SLC34A3, SLC3A1, SLC7A9, SPP1 …

### alopecia areata — associates (`Disease::DOID:986`, `DaG`)

**Question:** List every gene associated with the disease alopecia areata. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ITGA2B, ITGB3, CDKN1A, TNFSF4, STAT5B, PTPN6, MAPK8, FOS, JUN, NRAS, KRAS, HRAS, PIK3CA, PTEN, TP53, NOTCH1, RORC, RUNX1, TCF7L2, GATA3, IRF4, CCR9, IL2RA, IFNGR2, IL2RG, IL10RB, IL10RA, IL10R1, IL1RAPL1, IL1RN, IL18R1, IL18RC, IL18R2, IL23R, IL2RB, IL2RA, IL2RG, IL2ST, IL1RL1, IL1RL1B, IL1RL1C, IL1RL1D, IL1RL1E, IL1RL1F, IL1RL1G, IL1RL1H, IL1RL1I, IL1RL1J, IL1RL1K, IL1RL1L, IL1RL1M, IL1RL1N, IL1RL1O, IL1RL1P, IL1RL1Q, IL1RL1R, IL1RL1S, IL1RL1T, IL1RL1U, IL1RL1V, IL1RL
```

- Graph holds **12** facts; model stated **61**; **1** were correct.
- Coverage **8.3%**, precision **1.6%**
- Correct: IL2RA
- Invented (not in graph): ITGA2B, ITGB3, CDKN1A, TNFSF4, STAT5B, PTPN6, MAPK8, FOS, JUN, NRAS, KRAS, HRAS, PIK3CA, PTEN, TP53
- Missed: CD4, CD8A, CTLA4, CXCL10, CXCL9, CXCR3, IKZF4, PRDX5, RAET1L, STX17, ULBP3

### rectum cancer — associates (`Disease::DOID:1993`, `DaG`)

**Question:** List every gene associated with the disease rectum cancer. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TP53, KRAS, NRAS, SMAD4, PTEN, TP63, APC, MLH1, MSH2, DCC, CDH1, KRBBB1, STK11, PIK3CA, PIK3R1, PIK3CG, PIK3CB, PIK3R3, PIK3R2, AKT1, AKT2, AKT3, BRCA1, BRCA2, ATM, CHEK2, BARD1, PMS2, RAD50, MLH3, EPCAM, TGFBR2, TGFB1, TGFB2, TGFB3, VIM, CCNE1, CCND1, CCNB1, CCNB2, CIC, CTNNB1, NF1, NOTCH1, RARRES3, SFRP1, SFRP2, SFRP3, SFRP4, SFRP5, SFRP6, SFRP7, SFRP8, SFRP9, SFRP10, SFRP11, SFRP12, SFRP13, SFRP14, SFRP15, SFRP16, SFRP17, SFRP18, SFRP19, SFRP20, SFRP21
```

- Graph holds **17** facts; model stated **66**; **3** were correct.
- Coverage **17.6%**, precision **4.5%**
- Correct: TP53, KRAS, NRAS
- Invented (not in graph): SMAD4, PTEN, TP63, APC, MLH1, MSH2, DCC, CDH1, KRBBB1, STK11, PIK3CA, PIK3R1, PIK3CG, PIK3CB, PIK3R3
- Missed: CD6, DKKL1, HRAS, ITGA2, KRT20, KRT7, MYRF, RAB11B, RAB1A, SCRT1, SLC14A2, SMUG1, TYMS, ZXDC

### vascular cancer — associates (`Disease::DOID:175`, `DaG`)

**Question:** List every gene associated with the disease vascular cancer. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
VEGFA, VEGFB, VEGFC, VEGFD, KDR, KRAS, NRAS, HRAS, BCR-ABL, FLT3, NPM1, CEBPA, IDH1, IDH2, TP53, PIK3CA, PTEN, SMAD4, NOTCH1, JAK2, ABL1, BRAF, MET, EGFR, ERBB2, HER2, ALK, ROS1, FGFR1, FGFR2, FGFR3, FGFR4, PDGFRA, PDGFRB, PDGFRD, PDGFRG, KIT, CDKN2A, CDKN2B, CDKN2C, CDKN2D, CDKN2E, CDKN2F, CDKN2G, CDKN2H, CDKN2I, CDKN2J, CDKN2K, CDKN2L, CDKN2M, CDKN2N, CDKN2O, CDKN2P, CDKN2Q, CDKN2R, CDKN2S, CDKN2T, CDKN2U, CDKN2V, CDKN2W, CDKN2X, CDKN2Y, CDKN2Z, CDKN2AA, CDKN2AB, CDKN2AC, CDKN2AD, CDKN2AE, CDKN2AF, CD
```

- Graph holds **9** facts; model stated **70**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): VEGFA, VEGFB, VEGFC, VEGFD, KDR, KRAS, NRAS, HRAS, BCR-ABL, FLT3, NPM1, CEBPA, IDH1, IDH2, TP53
- Missed: CALD1, CAMTA1, CD34, HBA1, MITF, MLANA, TFE3, TSC2, WWTR1

### membranous glomerulonephritis — associates (`Disease::DOID:10976`, `DaG`)

**Question:** List every gene associated with the disease membranous glomerulonephritis. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
MMP9, TGFBR2, CD44, FN1, COL3A1, FBN1, ITGA5, VEGFA, PTPN22, TNFSF10
```

- Graph holds **27** facts; model stated **10**; **1** were correct.
- Coverage **3.7%**, precision **10.0%**
- Correct: MMP9
- Invented (not in graph): TGFBR2, CD44, FN1, COL3A1, FBN1, ITGA5, VEGFA, PTPN22, TNFSF10
- Missed: ABCA1, ALB, APOA1, APOE, C3, C7, CD40, CD40LG, CD79A, CFH, GAA, HLA-DQA1, HLA-DRB1, IL1B, LRP2, LRPAP1, NPHS1, NPHS2, PLA2G1B, PLA2R1, PLG, PTPRU, RHOA, SPARC, SPG7 …

### larynx cancer — associates (`Disease::DOID:2596`, `DaG`)

**Question:** List every gene associated with the disease larynx cancer. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TP53, RB1, SMAD4, CDKN2A, TP63, NOTCH1, PIK3CA, PTEN, KRAS, NF1, STK11, APC, BRCA2, TP73, SMARCB1, MYC, CCNE1, EGFR, MET, FGFR1, RAF1, NRAS, BRAF, PIK3R1, PIK3CD, PIK3CA, PIK3R3, PIK3CG, PIK3CE, PIK3R4, PIK3R5, PIK3R6, PIK3R7, PIK3R8, PIK3R9, PIK3R10, PIK3R11, PIK3R12, PIK3R13, PIK3R14, PIK3R15, PIK3R16, PIK3R17, PIK3R18, PIK3R19, PIK3R20, PIK3R21, PIK3R22, PIK3R23, PIK3R24, PIK3R25, PIK3R26, PIK3R27, PIK3R28, PIK3R29, PIK3R30, PIK
```

- Graph holds **5** facts; model stated **57**; **1** were correct.
- Coverage **20.0%**, precision **1.8%**
- Correct: TP53
- Invented (not in graph): RB1, SMAD4, CDKN2A, TP63, NOTCH1, PIK3CA, PTEN, KRAS, NF1, STK11, APC, BRCA2, TP73, SMARCB1, MYC
- Missed: ACOT13, HPD, OAF, PDPN

# Coverage report — what the model omits

**Model:** `Qwen/Qwen2.5-1.5B-Instruct`  
**Graph:** Hetionet v1.0 (Himmelstein et al. 2017), used as-is  
**Subjects:** 20, sampled with seed 0 from edges with 5–60 targets

Every number below is a count over graph edges. No judge model, no entailment score, no learned metric.

## Headline

| Measure | Value |
| --- | ---: |
| Facts the graph holds | 385 |
| Facts the model stated | 494 |
| Correct (in graph) | 8 |
| **Coverage** (of graph knowledge surfaced) | **2.1%** |
| **Precision** (of statements that were real) | **1.6%** |
| Subjects with ZERO correct facts | 17/20 |

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

### Testosterone — upregulates (`Compound::DB00624`, `CuG`)

**Question:** List every gene that the compound Testosterone upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
AR, BCL2L11, CYP19A1, DAX1, FOXD3, GNAS, HSD17B10, LHX8, MITF, NR5A1, PPARA, PRDM14, RORA, SRY, TCF7L2, VDR, WNT5A
```

- Graph holds **27** facts; model stated **17**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): AR, BCL2L11, CYP19A1, DAX1, FOXD3, GNAS, HSD17B10, LHX8, MITF, NR5A1, PPARA, PRDM14, RORA, SRY, TCF7L2
- Missed: CDK6, COPB2, CYTH1, DDIT4, EDEM1, FOXO3, GDPD5, GLRX, GPER1, HMOX1, HOMER2, IKZF1, INPP1, LGMN, LRRC16A, MALT1, NFKBIA, P4HA2, POLD4, RAB4A, SEC14L2, SERPINA3, SPAG4, SPDEF, TIPARP …

### Clarithromycin — downregulates (`Compound::DB01211`, `CdG`)

**Question:** List every gene that the compound Clarithromycin downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ACO2, CYP3A4, CYP3A5, CYP3A7, CYP2C19, CYP2D6, CYP2C9, CYP2C19, CYP2B6, CYP2E1, CYP2C8, CYP2C10, CYP2C19, CYP2C9, CYP2C19, CYP2C8, CYP2C10, CYP2C9, CYP2C19, CYP2C8, CYP2C10, CYP2C9, CYP2C19, CYP2C8, CYP2C10, CYP2C9, CYP2C19, CYP2C8, CYP2C10, CYP2C9, CYP2C19, CYP2C8, CYP2C10, CYP2C9, CYP2C19, CYP2C8, CYP2C10, CYP2C9, CYP2C19, CYP2C8, CYP2C10, CYP2C9, CYP2C19, CYP2C8, CYP2C10, CYP2C9, CYP2C19
```

- Graph holds **32** facts; model stated **47**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ACO2, CYP3A4, CYP3A5, CYP3A7, CYP2C19, CYP2D6, CYP2C9, CYP2C19, CYP2B6, CYP2E1, CYP2C8, CYP2C10, CYP2C19, CYP2C9, CYP2C19
- Missed: ARFIP2, CDC20, CHERP, CNDP2, COTL1, CSNK1E, DNAJA3, DNTTIP2, GDF15, GNPDA1, HTATSF1, KEAP1, LAP3, MIF, MSN, NME1, NOSIP, NPDC1, PDHX, PHB2, PHGDH, POLR2I, PPIE, PRAF2, RPS4Y1 …

### Risperidone — binds (`Compound::DB00734`, `CbG`)

**Question:** List every gene that the compound Risperidone binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
D2R, D3R, 5-HT1A, 5-HT2A, 5-HT2C, 5-HT6, GABAA, HTR2A, HTR2B, HTR3A, HTR4, HTR7, HTR8S1, HTR9, MCH, NPY, OXTR, PPARA, PTEN, SERT, TPH2, TRPV1, VIP, VIPR2
```

- Graph holds **25** facts; model stated **24**; **3** were correct.
- Coverage **12.0%**, precision **12.5%**
- Correct: HTR2A, HTR2B, HTR7
- Invented (not in graph): D2R, D3R, HT1A, HT2A, HT2C, HT6, GABAA, HTR3A, HTR4, HTR8S1, HTR9, MCH, NPY, OXTR, PPARA
- Missed: ABCB1, ADRA1A, ADRA1B, ADRA2A, ADRA2B, ADRA2C, CYP2D6, CYP3A4, CYP3A5, CYP3A7, CYP3A7-CYP3A51P, DRD1, DRD2, DRD3, DRD4, H1F0, HRH1, HTR1A, HTR1B, HTR1D, HTR2C, KCNH2

### Digoxin — binds (`Compound::DB00390`, `CbG`)

**Question:** List every gene that the compound Digoxin binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
GSK3B, KDR, KCNJ2, SCN5A
```

- Graph holds **22** facts; model stated **4**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): GSK3B, KDR, KCNJ2, SCN5A
- Missed: ABCB1, ABCB11, ATP1A1, ATP1A2, ATP1A3, ATP1A4, ATP1B1, ATP1B2, ATP1B3, CYP11A1, CYP3A4, FXYD2, SLC22A8, SLC51A, SLC51B, SLCO1A2, SLCO1B1, SLCO1B3, SLCO1C1, SLCO2B1, SLCO4A1, SLCO4C1

### Gabapentin — binds (`Compound::DB00996`, `CbG`)

**Question:** List every gene that the compound Gabapentin binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
GNAS, GABRA5, GABRB3, GABRG2, GABRR, GABRP
```

- Graph holds **5** facts; model stated **6**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): GNAS, GABRA5, GABRB3, GABRG2, GABRR, GABRP
- Missed: ADORA1, BCAT1, CACNA1B, CACNA2D1, CACNA2D2

### Methysergide — binds (`Compound::DB00247`, `CbG`)

**Question:** List every gene that the compound Methysergide binds. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
MTHFR, CYP2D6
```

- Graph holds **11** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): MTHFR, CYP2D6
- Missed: HTR1A, HTR1B, HTR1D, HTR1E, HTR1F, HTR2A, HTR2B, HTR2C, HTR6, HTR7, SIGMAR1

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

### Salmeterol — downregulates (`Compound::DB00938`, `CdG`)

**Question:** List every gene that the compound Salmeterol downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
SALTRKB1A, SALTRKB2, SALTRKB3
```

- Graph holds **14** facts; model stated **3**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): SALTRKB1A, SALTRKB2, SALTRKB3
- Missed: CCNA2, CCNB2, CDC20, IGFBP3, LDHB, MRPS2, MYC, PCNA, PRPF4, RUVBL1, STUB1, TIMELESS, TOP2A, TXNRD1

### Raltitrexed — downregulates (`Compound::DB00293`, `CdG`)

**Question:** List every gene that the compound Raltitrexed downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ABCA12, ABCB10, ABCD1, ABCG5, ABCG8, ADRB3, ATP7A, CYP2C9, CYP2C19, CYP2E1, CYP2F1, CYP2J2, CYP2R1, CYP2S1, CYP2U1, CYP4F2, CYP4F6, CYP4V2, DDX58, ESR1, FAM134A, GPR132, HLA-A, HLA-B, HLA-C, HLA-E, HLA-F, HLA-G, HLA-DR, HLA-DQ, HLA-DP, KIAA0319, LRP1, MUC1, NDUFB11, PDE4DIP, PRKAG2, SLC25A4, TCF7L2, UGT2B15, VPS13C, WFS1, XIST, YWHAE
```

- Graph holds **7** facts; model stated **44**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ABCA12, ABCB10, ABCD1, ABCG5, ABCG8, ADRB3, ATP7A, CYP2C9, CYP2C19, CYP2E1, CYP2F1, CYP2J2, CYP2R1, CYP2S1, CYP2U1
- Missed: AURKB, CDC20, KIF20A, PLA2G4A, PPP2R5E, PSRC1, VPS28

### Cefixime — downregulates (`Compound::DB00671`, `CdG`)

**Question:** List every gene that the compound Cefixime downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
NOX2, NOS3
```

- Graph holds **37** facts; model stated **2**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): NOX2, NOS3
- Missed: ACOT9, ADI1, ALDOA, ATP6V0B, BAG3, CLTB, COX8A, CSRP1, CYCS, DDIT4, DECR1, EBNA1BP2, EBP, EIF4EBP1, ERBB2, GAA, JMJD6, KDM3A, LRPAP1, LYPLA1, MIF, MRPS16, MTHFD2, MYL9, OXA1L …

### Chloramphenicol — downregulates (`Compound::DB00446`, `CdG`)

**Question:** List every gene that the compound Chloramphenicol downregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
ABCB1, ABCB4, ABCG2, ABCG5, ABCG8, ADRB3, ATP7A, CYP2C9, CYP2C19, CYP2E1, CYP2F1, CYP2J2, CYP2R1, CYP2S1, CYP2U1, CYP3A4, CYP3A5, CYP3A7, CYP4A01, CYP4F2, CYP4L1, CYP6B1, CYP6P1, CYP6P2, CYP6P3, CYP6P4, CYP6P5, CYP6P6, CYP6P7, CYP6P8, CYP6P9, CYP6P10, CYP6P11, CYP6P12, CYP6P13, CYP6P14, CYP6P15, CYP6P16, CYP6P17, CYP6P18, CYP6P19, CYP6P20, CYP6P21, CYP6P22, CYP6P23, CYP6P24, CYP6P25, CYP6P26, CYP6P27
```

- Graph holds **14** facts; model stated **49**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): ABCB1, ABCB4, ABCG2, ABCG5, ABCG8, ADRB3, ATP7A, CYP2C9, CYP2C19, CYP2E1, CYP2F1, CYP2J2, CYP2R1, CYP2S1, CYP2U1
- Missed: CCNB2, DLD, IFRD2, JMJD6, KRT7, OXA1L, PNMA2, PPP2R3C, RPS4Y1, S100A6, TIMM9, TPI1, UBE2S, USP22

### Tenofovir — upregulates (`Compound::DB00300`, `CuG`)

**Question:** List every gene that the compound Tenofovir upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
A2AR, ADRB1, ADRB2, ADRB3, ADRB4, ADRB5, ADRB6, ADRB7, ADRB8, ADRB9, ADRB10, ADRB11, ADRB12, ADRB13, ADRB14, ADRB15, ADRB16, ADRB17, ADRB18, ADRB19, ADRB20, ADRB21, ADRB22, ADRB23, ADRB24, ADRB25, ADRB26, ADRB27, ADRB28, ADRB29, ADRB30, ADRB31, ADRB32, ADRB33, ADRB34, ADRB35, ADRB36, ADRB37, ADRB38, ADRB39, ADRB40, ADRB41, ADRB42, ADRB43, ADRB44, ADRB45, ADRB46, ADRB47, ADRB48, ADRB49, ADRB50, ADRB51
```

- Graph holds **12** facts; model stated **52**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): A2AR, ADRB1, ADRB2, ADRB3, ADRB4, ADRB5, ADRB6, ADRB7, ADRB8, ADRB9, ADRB10, ADRB11, ADRB12, ADRB13, ADRB14
- Missed: BUB1B, C2CD2, CASP10, CCL2, CDK6, EGF, EXT1, IPO13, KIT, PIGB, RBM15B, SLC35A1

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

### Icosapent — upregulates (`Compound::DB00159`, `CuG`)

**Question:** List every gene that the compound Icosapent upregulates. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
Apolipoprotein E, Apolipoprotein J, Lipoprotein(a)
```

- Graph holds **7** facts; model stated **3**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): Apolipoprotein E, Apolipoprotein J, Lipoprotein
- Missed: CSTA, E2F2, EPCAM, FAS, RBP4, SPDEF, TBP

### Barrett's esophagus — associates (`Disease::DOID:9206`, `DaG`)

**Question:** List every gene associated with the disease Barrett's esophagus. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TP53, CDKN2A, SMAD4, KRAS, NF1, PTEN, TP63, RB1, MYC, NOTCH1, PIK3CA, MAPK1, BRCA2, STK11, TGFBR2, DCC, FBLN5, GDF15, PAX8, RARRES2, SFRP1, WNT7B, TGFB1, VIM
```

- Graph holds **24** facts; model stated **24**; **2** were correct.
- Coverage **8.3%**, precision **8.3%**
- Correct: TP53, CDKN2A
- Invented (not in graph): SMAD4, KRAS, NF1, PTEN, TP63, RB1, MYC, NOTCH1, PIK3CA, MAPK1, BRCA2, STK11, TGFBR2, DCC, FBLN5
- Missed: APC, ATP4A, BARX1, BMP4, CDH13, CDX2, CRTC1, CXCL8, CYP26A1, FOXF1, FOXP1, GAST, HGF, MCL1, NR1I2, PPARG, PTGES, PTGS2, RELA, RPRM, SLC9A1, SST

### narcolepsy — associates (`Disease::DOID:8986`, `DaG`)

**Question:** List every gene associated with the disease narcolepsy. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
DRD2, HTR1A, HTR3B, HTR4, HTR5A, HTR6, HTR7, HTR8S1, HTR9, KCNJ11, KCH, MAPT, NRXN1, NRG1, OPRM1, PDE10A, PRKAR1A, SCN3A, SCN4A, SCN10A, SLC6A4, TPH2, UBE3A
```

- Graph holds **27** facts; model stated **23**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): DRD2, HTR1A, HTR3B, HTR4, HTR5A, HTR6, HTR7, HTR8S1, HTR9, KCNJ11, KCH, MAPT, NRXN1, NRG1, OPRM1
- Missed: CALR3, CHKB, CPT1B, CTNNBL1, HCRT, HCRTR1, HCRTR2, HLA-DQA1, HLA-DQB1, HLA-DRB1, HRH3, HTR2A, IL10RB, NPS, P2RY11, PENK, PPAN, SOCS2, TAC1, TNF, TNFRSF1B, TOR1B, TRA, TRB, TRH …

### cleft lip — associates (`Disease::DOID:9296`, `DaG`)

**Question:** List every gene associated with the disease cleft lip. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
TCF2, BMP4, FGFR1, NOTCH3, PAX9, TGFB2
```

- Graph holds **54** facts; model stated **6**; **3** were correct.
- Coverage **5.6%**, precision **50.0%**
- Correct: BMP4, FGFR1, PAX9
- Invented (not in graph): TCF2, NOTCH3, TGFB2
- Missed: ABCA4, ALX3, ARHGAP29, BCL3, BHMT2, CLPTM1, CLPTM1L, CRISPLD2, EPHA3, FGF10, FGF2, FGF3, FGF7, FGF8, FGF9, FGFR2, FGFR3, GSDMC, IRF6, MAFB, MSX1, MTHFR, MTHFS, MTR, MYC …

### idiopathic pulmonary fibrosis — associates (`Disease::DOID:0050156`, `DaG`)

**Question:** List every gene associated with the disease idiopathic pulmonary fibrosis. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
IDUA, CYP2C9, FBN1, COL4A3, COL4A4, COL4A5, CTNNB1, TGFBR2, BMPR2, SMAD4, FGFR3, VEGFC, MMP17, IL6, TNFA, CXCL8, IFITM1, NFKB1, IRF5, STAT3, MAPK1, JUN, ESR1, HLA-DRB1, HLA-DQA1, HLA-DQB1, HLA-DRB4, HLA-DRB5, HLA-DRA, HLA-DRB1, HLA-DRB2, HLA-DRB3, HLA-DPB1, HLA-DPQ1, HLA-DPA1, HLA-DPA2, HLA-DPA3, HLA-DPB2, HLA-DPC1, HLA-DPE1, HLA-DPF1, HLA-DPG1, HLA-DPI1, HLA-DPM1, HLA-DPR1, HLA-DPS1, HLA-DPT1, HLA-DPU1, HLA-DPV1, HLA-DPW1, HLA-DPY1, HLA-DQG1, HLA-DQH1, HLA-DQJ1, HLA-DQL1, HLA-DQM1,
```

- Graph holds **18** facts; model stated **56**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): IDUA, CYP2C9, FBN1, COL4A3, COL4A4, COL4A5, CTNNB1, TGFBR2, BMPR2, SMAD4, FGFR3, VEGFC, MMP17, IL6, TNFA
- Missed: ATP11A, DPP9, DSP, ELMOD2, FAM13A, FN1, FOSL2, MUC5B, OBFC1, PLAU, SFTPA1, SFTPA2, SFTPC, SFTPD, SMAD3, TERT, TGFB1, TOLLIP

### nephrolithiasis — associates (`Disease::DOID:585`, `DaG`)

**Question:** List every gene associated with the disease nephrolithiasis. Answer with gene symbols separated by commas, nothing else.

**Model answered verbatim:**

```
NPHS1, NPHS2, KCNJ5, CYP4F2, FBN1, COL8A3, COL8A5, TNNI3, MYH11, TPM3, LRP1, PTPN22, CDKN2B-AS1, DUSP9, SLC26A3, ATP7B, CLCNKB, SCN1A, SCN2A, SCN3A, SCN4A, SCN5A, SCN8A, KCNE1, KCNH2, KCNE2, KCNE3, KCNA5, KCNB1, KCND2, KCNE4, KCNE5, KCNE6, KCNE7, KCNE8, KCNE9, KCNE10, KCNE11, KCNE12, KCNE13, KCNE14, KCNE15, KCNE16, KCNE17, KCNE18, KCNE19, KCNE20, KCNE21, KCNE22, KCNE23, KCNE24, KCNE25, KCNE26, KCNE27, KCNE28, KCNE29, KCNE30, KCNE31, KCNE32, KCNE33, KCNE34, KCNE35, KCNE36, KCNE37
```

- Graph holds **26** facts; model stated **64**; **0** were correct.
- Coverage **0.0%**, precision **0.0%**
- Correct: (none)
- Invented (not in graph): NPHS1, NPHS2, KCNJ5, CYP4F2, FBN1, COL8A3, COL8A5, TNNI3, MYH11, TPM3, LRP1, PTPN22, CDKN2B-AS1, DUSP9, SLC26A3
- Missed: ADCY10, AGXT, AMBP, APRT, AQP1, ATP6V0A4, CHRM3, CLCN4, CLCN5, CLDN14, CLDN16, DGKH, GRHPR, PFN3, PTH, RGS14, SLC22A12, SLC26A1, SLC26A6, SLC2A9, SLC34A1, SLC34A3, SLC3A1, SLC7A9, SPP1 …

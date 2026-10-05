# Coverage — frontier model

**Model:** claude-opus-5 (parametric memory only, no retrieval, no graph access)  
**Graph:** Hetionet v1.0, used as-is  
**Protocol:** Questions generated with seed 7. Answers written before any gold data was displayed in the session. Subjects from the seed-0 run (Thiamine, Testosterone, Clarithromycin) were excluded to avoid contamination.

## Headline

| Measure | Value |
| --- | ---: |
| Facts the graph holds | 427 |
| Facts the model stated | 152 |
| Statements that are real gene symbols | 150 |
| Correct for their subject | 63 |
| **Coverage** | **14.8%** |
| **Precision** | **41.4%** |
| Subjects with zero correct | 6/20 |
| Subjects abstained | 1/20 |

## By relation type

| Relation | Subjects | Graph facts | Stated | Correct | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| CbG (binds) | 5 | 91 | 31 | 18 | 19.8% |
| CdG (downregulates) | 5 | 96 | 27 | 2 | 2.1% |
| CuG (upregulates) | 5 | 110 | 35 | 3 | 2.7% |
| DaG (associates) | 5 | 130 | 59 | 40 | 30.8% |

## Rows

### Nitrofural — downregulates (`Compound::DB00336`, `CdG`)

**Model said:** (abstained)

**Graph holds (12):** CRYZ, DDAH1, HDAC2, ISOC1, ITGAE, ITGB1BP1, KIF20A, NVL, PPP2R5E, S100A6, TMEM50A, TXNDC9

- correct **0/12** (coverage 0.0%, precision 0.0%)
- hit: (none)
- not in graph: (none)

### Quinidine — binds (`Compound::DB00908`, `CbG`)

**Model said:** KCNH2, SCN5A, KCNQ1, CACNA1C, CYP2D6, ABCB1, KCNJ2, CHRM2

**Graph holds (29):** ABCB1, ABCB11, ABCC2, CHRM2, CYP1A1, CYP1A2, CYP2B6, CYP2C8, CYP2C9, CYP2D6, CYP2E1, CYP3A4, CYP3A7, CYP3A7-CYP3A51P, KCNH2, KCNK1, KCNK6, ORM1, SCN1A, SCN2A, SCN3A, SCN5A, SLC22A1, SLC22A2, SLC22A4, SLC22A5, SLC22A8, SLCO1A2, SLCO1B1

- correct **5/29** (coverage 17.2%, precision 62.5%)
- hit: KCNH2, SCN5A, CYP2D6, ABCB1, CHRM2
- not in graph: KCNQ1, CACNA1C, KCNJ2

### Flutamide — downregulates (`Compound::DB00499`, `CdG`)

**Model said:** AR, KLK3, TMPRSS2, FKBP5, NKX3-1, CDK1, CCNB1

**Graph holds (10):** ADI1, ATP6V1D, CCNB1, GNAS, HMGCR, HMGCS1, INSIG1, KDM3A, MBOAT7, PCNA

- correct **1/10** (coverage 10.0%, precision 14.3%)
- hit: CCNB1
- not in graph: AR, KLK3, TMPRSS2, FKBP5, NKX3-1, CDK1

### Fenofibrate — upregulates (`Compound::DB01039`, `CuG`)

**Model said:** PPARA, CPT1A, ACOX1, FABP1, APOA1, APOA2, PDK4, ANGPTL4, HMGCS2, SLC25A20

**Graph holds (8):** CSTA, HLA-DRA, HTRA1, IL4R, KIT, MAP7, NR1H2, SOX2

- correct **0/8** (coverage 0.0%, precision 0.0%)
- hit: (none)
- not in graph: PPARA, CPT1A, ACOX1, FABP1, APOA1, APOA2, PDK4, ANGPTL4, HMGCS2, SLC25A20

### Bortezomib — binds (`Compound::DB00188`, `CbG`)

**Model said:** PSMB5, PSMB1, PSMB2, PSMB8, PSMB9, PSMA1, PSMD1

**Graph holds (17):** CTSG, CYP1A1, CYP1A2, CYP2C19, CYP2C8, CYP2C9, CYP2D6, CYP3A4, PSMA1, PSMB1, PSMB2, PSMB5, PSMB8, PSMD1, PSMD2, PTGS1, SLC31A1

- correct **6/17** (coverage 35.3%, precision 85.7%)
- hit: PSMB5, PSMB1, PSMB2, PSMB8, PSMA1, PSMD1
- not in graph: PSMB9

### Ergocalciferol — binds (`Compound::DB00153`, `CbG`)

**Model said:** VDR, GC, CYP2R1, CYP27B1, CYP24A1, RXRA

**Graph holds (7):** AR, CYP24A1, CYP27A1, CYP27B1, CYP2R1, CYP3A4, VDR

- correct **4/7** (coverage 57.1%, precision 66.7%)
- hit: VDR, CYP2R1, CYP27B1, CYP24A1
- not in graph: GC, RXRA

### Prednicarbate — upregulates (`Compound::DB01130`, `CuG`)

**Model said:** NR3C1, FKBP5, TSC22D3, KLF15, PER1, ZBTB16, DUSP1

**Graph holds (8):** IKBKB, PEX11A, PRR15L, RAB27A, SERPINA3, SSBP2, TSC22D3, WASF3

- correct **1/8** (coverage 12.5%, precision 14.3%)
- hit: TSC22D3
- not in graph: NR3C1, FKBP5, KLF15, PER1, ZBTB16, DUSP1

### Calcitriol — downregulates (`Compound::DB00136`, `CdG`)

**Model said:** CYP27B1, PTH, IL2, IFNG, CCND1, MYC, CDKN1A

**Graph holds (19):** CCDC86, CCL2, CD320, GAS2L1, GNB5, HPRT1, IER3, LRPAP1, MYC, NT5DC2, NUCB2, NUP85, PLA2G15, PPP2R5E, PRPF4, RPIA, RRP1B, SH3BP5, UTP18

- correct **1/19** (coverage 5.3%, precision 14.3%)
- hit: MYC
- not in graph: CYP27B1, PTH, IL2, IFNG, CCND1, CDKN1A

### Escitalopram — binds (`Compound::DB01175`, `CbG`)

**Model said:** SLC6A4, HTR2A, HTR1A

**Graph holds (10):** ADRA1A, CHRM1, CYP2C19, CYP2D6, CYP3A4, HRH1, HTR2C, SLC6A2, SLC6A3, SLC6A4

- correct **1/10** (coverage 10.0%, precision 33.3%)
- hit: SLC6A4
- not in graph: HTR2A, HTR1A

### Phenobarbital — binds (`Compound::DB01174`, `CbG`)

**Model said:** GABRA1, GABRB2, GABRG2, NR1I2, NR1I3, CYP2B6, GABRA2

**Graph holds (28):** ABCB1, ABCB11, ABCC1, ABCC2, ABCC3, CHRFAM7A, CHRNA4, CHRNA7, CYP1A1, CYP1A2, CYP1B1, CYP2A6, CYP2B6, CYP2C18, CYP2C19, CYP2C8, CYP2C9, CYP2E1, CYP3A4, CYP3A5, CYP3A7, CYP3A7-CYP3A51P, CYP4A11, CYP4B1, GABRA1, GRIA2, GRIK2, SLCO2A1

- correct **2/28** (coverage 7.1%, precision 28.6%)
- hit: GABRA1, CYP2B6
- not in graph: GABRB2, GABRG2, NR1I2, NR1I3, GABRA2

### Colchicine — downregulates (`Compound::DB01394`, `CdG`)

**Model said:** TUBB, TUBA1A, IL1B, TNF, SELE, NLRP3, CCL2

**Graph holds (44):** ADH5, AKR7A2, B4GAT1, BET1, C1RL, C2CD5, CCNE2, CDK1, CHEK2, COPS7A, CPNE3, DTL, EAPP, ESR1, FIS1, GATA3, GNPDA1, GOLPH3L, HADH, HIST1H2BK, HSPA1A, ISOC1, MAT2B, MCM3, MCM6, MELK, MPC2, MTHFD2, NET1, NFKBIA, PCNA, PEX11B, RNASE4, THTPA, TMED10, TOMM70A, TOP2A, TOPBP1, TXNDC9, UBE2A, UBE2C, UGDH, WDR5B, XBP1

- correct **0/44** (coverage 0.0%, precision 0.0%)
- hit: (none)
- not in graph: TUBB, TUBA1A, IL1B, TNF, SELE, NLRP3, CCL2

### Ethacrynic acid — upregulates (`Compound::DB00903`, `CuG`)

**Model said:** HMOX1, NQO1, HSPA1A, GSTP1, TXNRD1, SLC12A1

**Graph holds (26):** ABCB6, ABHD4, AKR1C1, AKR1C2, CBR1, CDKN1A, CTSL, FAS, FOSL1, GCLM, GPC1, HMOX1, INPP1, KEAP1, KIAA0355, LRP10, MVP, P4HA2, PRSS23, RAP1GAP, RRP8, SESN1, SQSTM1, TMEM2, TXNRD1, UGDH

- correct **2/26** (coverage 7.7%, precision 33.3%)
- hit: HMOX1, TXNRD1
- not in graph: NQO1, HSPA1A, GSTP1, SLC12A1

### Cyclophosphamide — downregulates (`Compound::DB00531`, `CdG`)

**Model said:** MKI67, CCNB1, TOP2A, CDK1, AURKA, BRCA1

**Graph holds (11):** ADI1, ATP6V0B, CDK4, CHMP4A, CNDP2, DLD, EBNA1BP2, ENOPH1, MTHFD2, S100A13, USP22

- correct **0/11** (coverage 0.0%, precision 0.0%)
- hit: (none)
- not in graph: MKI67, CCNB1, TOP2A, CDK1, AURKA, BRCA1

### Pazopanib — upregulates (`Compound::DB06589`, `CuG`)

**Model said:** HMOX1, DDIT3, VEGFA, KDR, FLT1, PDGFRB

**Graph holds (59):** ANXA7, ATP5S, BCL7B, CBX3, CDCA4, CGRRF1, CHEK2, CPVL, CRIP1, CXCL8, CYTH1, EBNA1BP2, EIF4EBP1, FAM216A, FKBP14, FOXJ3, GLOD4, GSS, ICAM3, IER3, IL1R2, KIAA0355, LPL, LYPLA1, LYRM1, METRN, MNAT1, MRPS16, MTHFD2, NUP93, POLE2, POLR2G, PPP1CA, PPP2R3C, PSMB8, PSME1, PSMG1, PXMP2, RAD9A, RAE1, RCHY1, RELB, RPA3, RPP30, SCAND1, SCP2, SDHB, SELL, SERPINA3, SLC35A3, SNX11, SRC, SRPRB, TBP, TMEM11, TOMM34, TSPAN3, TSPAN8, XBP1

- correct **0/59** (coverage 0.0%, precision 0.0%)
- hit: (none)
- not in graph: HMOX1, DDIT3, VEGFA, KDR, FLT1, PDGFRB

### Tacrolimus — upregulates (`Compound::DB00864`, `CuG`)

**Model said:** FKBP1A, PPP3CA, NFATC1, IL2, TGFB1, MTOR

**Graph holds (9):** AXIN1, CCNA1, DDIT4, LPL, PRKAG2, SQRDL, ST6GALNAC2, TLR4, TSC22D3

- correct **0/9** (coverage 0.0%, precision 0.0%)
- hit: (none)
- not in graph: FKBP1A, PPP3CA, NFATC1, IL2, TGFB1, MTOR

### malaria — associates (`Disease::DOID:12365`, `DaG`)

**Model said:** HBB, G6PD, ACKR1, HBA1, HBA2, ABO, CD36, ICAM1, TNF, NOS2, IL10, CR1, SLC4A1, HP

**Graph holds (49):** ABO, ACKR1, CD36, CD4, CD40LG, CD8A, CISH, CR1, CRP, DECR1, DHFR, DHODH, FAS, FCGR2A, FCGR2B, G6PD, GYPA, GYPC, HBB, HLA-B, HP, HPGDS, ICAM1, IFNG, IL10, IL12B, IL15, IL18, IL1B, IL2, IL4, IL6, KDR, KRT83, LTBR, MPG, NANP, NCR3, NOS2, PKLR, RPAP3, SCARB1, SCARB2, SLC4A1, SPINK5, TIRAP, TLR4, TLR9, TNF

- correct **12/49** (coverage 24.5%, precision 85.7%)
- hit: HBB, G6PD, ACKR1, ABO, CD36, ICAM1, TNF, NOS2, IL10, CR1, SLC4A1, HP
- not in graph: HBA1, HBA2

### Paget's disease of bone — associates (`Disease::DOID:5408`, `DaG`)

**Model said:** SQSTM1, TNFRSF11A, TNFRSF11B, CSF1, OPTN, DCSTAMP, VCP, NUP205, RIN3, TM7SF4

**Graph holds (16):** ALPL, ALPP, ALPPL2, BGLAP, CALCA, CSF1, DCSTAMP, INPP5D, NUP205, OPTN, PML, RIN3, SQSTM1, TNFRSF11A, TNFRSF11B, VCP

- correct **9/16** (coverage 56.2%, precision 90.0%)
- hit: SQSTM1, TNFRSF11A, TNFRSF11B, CSF1, OPTN, DCSTAMP, VCP, NUP205, RIN3
- not in graph: TM7SF4

### attention deficit hyperactivity disorder — associates (`Disease::DOID:1094`, `DaG`)

**Model said:** DRD4, DRD5, SLC6A3, SLC6A4, HTR1B, SNAP25, DBH, ADGRL3, COMT, MAOA, NOS1, TPH2

**Graph holds (41):** ADRA2A, ADRA2C, ANK3, AS3MT, BDNF, CACNA1C, CACNB2, CCDC68, CHRNA4, COMT, CSMD1, DPYD, DRD1, DRD2, DRD3, DRD4, DRD5, EFS, EP300, GABRQ, GRM7, HRH3, HTR1B, HTR2A, IMPACT, ITIH3, MAOA, MB21D1, MMP16, POLR3A, RTN4, SLC6A3, SLC6A4, SLC9A9, SNAP23, SNAP25, SNAP29, STUB1, SYNE1, TENM4, TPH2

- correct **9/41** (coverage 22.0%, precision 75.0%)
- hit: DRD4, DRD5, SLC6A3, SLC6A4, HTR1B, SNAP25, COMT, MAOA, TPH2
- not in graph: DBH, ADGRL3, NOS1

### Fuchs' endothelial dystrophy — associates (`Disease::DOID:11555`, `DaG`)

**Model said:** TCF4, COL8A2, SLC4A11, ZEB1, AGBL1, LOXHD1, KANK4, ATP1B1, TCF8

**Graph holds (6):** COL8A1, COL8A2, FBXO7, ITGBL1, PTPRG, TCF4

- correct **2/6** (coverage 33.3%, precision 22.2%)
- hit: TCF4, COL8A2
- not in graph: SLC4A11, ZEB1, AGBL1, LOXHD1, KANK4, ATP1B1, TCF8

### gout — associates (`Disease::DOID:13189`, `DaG`)

**Model said:** SLC2A9, ABCG2, SLC22A12, SLC17A1, SLC17A3, GCKR, PDZK1, SLC16A9, INHBC, RREB1, NRXN2, ALDH16A1, NLRP3, SLC22A11

**Graph holds (18):** ABCG2, ALDH16A1, BCKDHA, CASP1, HPRT1, IL15, IL1RN, LRRC16A, NLRP3, POMC, PRPS1, PRPS2, SLC17A1, SLC17A3, SLC22A11, SLC22A12, SLC2A9, UMOD

- correct **8/18** (coverage 44.4%, precision 57.1%)
- hit: SLC2A9, ABCG2, SLC22A12, SLC17A1, SLC17A3, ALDH16A1, NLRP3, SLC22A11
- not in graph: GCKR, PDZK1, SLC16A9, INHBC, RREB1, NRXN2

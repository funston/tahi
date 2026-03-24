# Spider Database Information

Generated: 2025-09-11 13:42:49

Comprehensive analysis of Spider 2.0 database complexity and size.

## Summary Statistics

- **Total Databases Analyzed**: 152
- **Accessible Databases**: 152
- **Total Tables**: 12,757
- **Total Columns**: 564,685
- **Total Estimated Rows**: 59,918,063,330

## Database Complexity Categories

- **Highly Complex (>1000 columns)**: 39 databases
- **Medium Complex (100-1000 columns)**: 52 databases
- **Less Complex (<100 columns)**: 61 databases

## Top 20 Most Complex Databases (by columns)

| Database                                               | Tables | Columns | Est. Rows      | Complexity |
|-------------------------------------------------------|-------:|--------:|---------------:|------------|
| FEC                                                   |    486 |  71,832 |    551,049,355 | 🔴 High     |
| COVID19_USA                                           |    285 |  70,858 |      9,289,501 | 🔴 High     |
| CENSUS_BUREAU_ACS_1                                   |    351 |  69,170 |      4,414,432 | 🔴 High     |
| SDOH                                                  |    294 |  68,863 |      4,417,166 | 🔴 High     |
| CENSUS_BUREAU_ACS_2                                   |    296 |  68,434 |      4,267,221 | 🔴 High     |
| GITHUB_REPOS_DATE                                     |  5,173 |  46,537 |    528,083,235 | 🔴 High     |
| BLS                                                   |    143 |  23,193 |     18,207,063 | 🔴 High     |
| GOOGLE_DEI                                            |    140 |  23,123 |     18,024,101 | 🔴 High     |
| GNOMAD                                                |     71 |  10,264 |    987,103,251 | 🔴 High     |
| NOAA_DATA_PLUS                                        |    234 |   7,450 |    742,276,079 | 🔴 High     |
| NOAA_DATA                                             |    218 |   7,275 |    742,092,583 | 🔴 High     |
| HTAN_1                                                |    200 |   7,030 |  5,819,795,740 | 🔴 High     |
| GA360                                                 |    366 |   5,522 |        903,653 | 🔴 High     |
| EBI_CHEMBL                                            |    785 |   5,337 |    522,698,820 | 🔴 High     |
| TCGA_MITELMAN                                         |    176 |   4,272 |    135,541,478 | 🔴 High     |
| TCGA                                                  |    157 |   4,107 |    132,611,047 | 🔴 High     |
| COVID19_JHU_WORLD_BANK                                |     25 |   3,770 |     24,413,793 | 🔴 High     |
| NEW_YORK_NOAA                                         |    119 |   3,571 |  1,801,492,788 | 🔴 High     |
| HTAN_2                                                |     94 |   3,428 |     24,926,156 | 🔴 High     |
| NEW_YORK_CITIBIKE_1                                   |    117 |   3,303 |    233,111,096 | 🔴 High     |

## Top 20 Largest Databases (by estimated rows)

| Database                                               | Tables | Columns | Est. Rows      | Complexity |
|-------------------------------------------------------|-------:|--------:|---------------:|------------|
| PANCANCER_ATLAS_2                 |     21 |   1,634 |  8,852,666,073 | 🔴 High     |
| HTAN_1                            |    200 |   7,030 |  5,819,795,740 | 🔴 High     |
| NEW_YORK_GHCN                     |    288 |   2,624 |  4,516,559,135 | 🔴 High     |
| OPEN_TARGETS_GENETICS_1           |     13 |     293 |  4,129,628,057 | 🟡 Medium   |
| OPEN_TARGETS_GENETICS_2           |     13 |     293 |  4,129,628,057 | 🟡 Medium   |
| GBIF                              |      1 |      50 |  3,025,858,163 | 🟢 Low      |
| GHCN_D                            |    266 |   2,141 |  2,889,052,950 | 🔴 High     |
| OPENAQ                            |     33 |     891 |  2,443,320,195 | 🟡 Medium   |
| EPA_HISTORICAL_AIR_QUALITY        |     32 |     879 |  2,437,725,581 | 🟡 Medium   |
| CMS_DATA                          |     52 |     865 |  2,181,075,029 | 🟡 Medium   |
| NEW_YORK_PLUS                     |     43 |     845 |  2,126,642,588 | 🟡 Medium   |
| NEW_YORK_NOAA                     |    119 |   3,571 |  1,801,492,788 | 🔴 High     |
| NEW_YORK_GEO                      |     38 |     658 |  1,627,689,681 | 🟡 Medium   |
| NEW_YORK                          |     22 |     483 |  1,627,506,185 | 🟡 Medium   |
| GNOMAD                            |     71 |  10,264 |    987,103,251 | 🔴 High     |
| STACKOVERFLOW_PLUS                |     24 |     345 |    745,472,735 | 🟡 Medium   |
| NOAA_DATA_PLUS                    |    234 |   7,450 |    742,276,079 | 🔴 High     |
| NOAA_DATA                         |    218 |   7,275 |    742,092,583 | 🔴 High     |
| PATENTS_USPTO                     |     46 |     444 |    669,659,537 | 🟡 Medium   |
| STACKOVERFLOW                     |     16 |     228 |    637,122,277 | 🟡 Medium   |

## Complete Database List (Sorted by Complexity Level)

### 🟢 Low Complexity Databases (61 total, <100 columns)

| Database                                               | Tables | Columns | Est. Rows      | Complexity |
|-------------------------------------------------------|-------:|--------:|---------------:|------------|
| GBIF                                                  |      1 |      50 |  3,025,858,163 | 🟢 Low      |
| GOOGLE_TRENDS                                         |      4 |      34 |    498,463,514 | 🟢 Low      |
| CHICAGO                                               |      2 |      45 |    219,833,989 | 🟢 Low      |
| NOAA_GLOBAL_FORECAST_SYSTEM                           |     11 |      90 |    218,374,323 | 🟢 Low      |
| GEO_OPENSTREETMAP_WORLDPOP                            |     11 |      94 |    217,152,521 | 🟢 Low      |
| GEO_OPENSTREETMAP                                     |     10 |      86 |    217,137,548 | 🟢 Low      |
| OPEN_IMAGES                                           |      4 |      30 |    103,933,912 | 🟢 Low      |
| PYPI                                                  |      2 |      45 |     86,867,269 | 🟢 Low      |
| DEPS_DEV_V1                                           |     10 |      78 |     80,030,681 | 🟢 Low      |
| HACKER_NEWS                                           |      1 |      14 |     41,855,814 | 🟢 Low      |
| IOWA_LIQUOR_SALES_PLUS                                |      3 |      36 |     33,290,963 | 🟢 Low      |
| IOWA_LIQUOR_SALES                                     |      1 |      24 |     30,082,002 | 🟢 Low      |
| DEATH                                                 |     28 |      99 |     18,358,312 | 🟢 Low      |
| LONDON                                                |      2 |      39 |     13,522,851 | 🟢 Low      |
| USA_NAMES                                             |      2 |      10 |     11,863,956 | 🟢 Low      |
| GITHUB_REPOS                                          |      6 |      34 |      7,617,607 | 🟢 Low      |
| ETHEREUM_BLOCKCHAIN                                   |      7 |      88 |      3,556,490 | 🟢 Low      |
| THELOOK_ECOMMERCE                                     |      7 |      73 |      3,339,950 | 🟢 Low      |
| COVID19_NYT                                           |      4 |      29 |      3,330,494 | 🟢 Low      |
| WORD_VECTORS_US                                       |      3 |      19 |      2,427,368 | 🟢 Low      |
| AIRLINES                                              |      8 |      35 |      2,289,506 | 🟢 Low      |
| CENSUS_GALAXY__ZIP_CODE_TO_BLOCK_GROUP_SAMPLE         |      8 |      57 |      2,262,153 | 🟢 Low      |
| CENSUS_GALAXY__AIML_MODEL_DATA_ENRICHMENT_SAMPLE      |      8 |      57 |      2,262,153 | 🟢 Low      |
| BRAZILIAN_E_COMMERCE                                  |     10 |      62 |      1,583,873 | 🟢 Low      |
| E_COMMERCE                                            |     11 |      70 |      1,559,764 | 🟢 Low      |
| ELECTRONIC_SALES                                      |      9 |      61 |      1,550,922 | 🟢 Low      |
| PATENTS_GOOGLE                                        |      4 |      87 |      1,244,366 | 🟢 Low      |
| CYMBAL_INVESTMENTS                                    |      1 |      14 |      1,222,562 | 🟢 Low      |
| DELIVERY_CENTER                                       |      7 |      59 |      1,154,523 | 🟢 Low      |
| MODERN_DATA                                           |     17 |      77 |      1,068,993 | 🟢 Low      |
| EDUCATION_BUSINESS                                    |     18 |      98 |        994,859 | 🟢 Low      |
| PATENTS                                               |      3 |      79 |        822,932 | 🟢 Low      |
| THE_MET                                               |      3 |      61 |        801,761 | 🟢 Low      |
| WWE                                                   |     10 |      35 |        578,899 | 🟢 Low      |
| TARGETOME_REACTOME                                    |      9 |      58 |        495,226 | 🟢 Low      |
| GOOGLE_ADS                                            |      2 |      16 |        480,945 | 🟢 Low      |
| IPL                                                   |      8 |      52 |        293,471 | 🟢 Low      |
| DB_IMDB                                               |     13 |      50 |        154,676 | 🟢 Low      |
| BASEBALL                                              |      2 |      46 |        120,178 | 🟢 Low      |
| IMDB_MOVIES                                           |      7 |      38 |         75,898 | 🟢 Low      |
| SUNROOF_SOLAR                                         |      2 |      64 |         68,456 | 🟢 Low      |
| SQLITE_SAKILA                                         |     16 |      89 |         46,273 | 🟢 Low      |
| PAGILA                                                |     16 |      89 |         46,273 | 🟢 Low      |
| CHINOOK                                               |     13 |      69 |         15,632 | 🟢 Low      |
| MUSIC                                                 |     11 |      64 |         15,607 | 🟢 Low      |
| STACKING                                              |      7 |      40 |         10,297 | 🟢 Low      |
| NORTHWIND                                             |     15 |      95 |          3,366 | 🟢 Low      |
| BBC                                                   |      1 |       4 |          2,225 | 🟢 Low      |
| BOWLINGLEAGUE                                         |     12 |      56 |          2,160 | 🟢 Low      |
| ENTERTAINMENTAGENCY                                   |     13 |      76 |          1,654 | 🟢 Low      |
| LOG                                                   |     19 |      88 |            854 | 🟢 Low      |
| SCHOOL_SCHEDULING                                     |     16 |      77 |            818 | 🟢 Low      |
| FINANCE__ECONOMICS                                    |      0 |       0 |              0 | 🟢 Low      |
| US_REAL_ESTATE                                        |      0 |       0 |              0 | 🟢 Low      |
| BRAZE_USER_EVENT_DEMO_DATASET                         |      0 |       0 |              0 | 🟢 Low      |
| NETHERLANDS_OPEN_MAP_DATA                             |      0 |       0 |              0 | 🟢 Low      |
| GLOBAL_WEATHER__CLIMATE_DATA_FOR_BI                   |      0 |       0 |              0 | 🟢 Low      |
| GLOBAL_GOVERNMENT                                     |      0 |       0 |              0 | 🟢 Low      |
| WEATHER__ENVIRONMENT                                  |      0 |       0 |              0 | 🟢 Low      |
| US_ADDRESSES__POI                                     |      0 |       0 |              0 | 🟢 Low      |
| YES_ENERGY__SAMPLE_DATA                               |      0 |       0 |              0 | 🟢 Low      |

### 🟡 Medium Complexity Databases (52 total, 100-1000 columns)

| Database                                               | Tables | Columns | Est. Rows      | Complexity |
|-------------------------------------------------------|-------:|--------:|---------------:|------------|
| OPEN_TARGETS_GENETICS_1                               |     13 |     293 |  4,129,628,057 | 🟡 Medium   |
| OPEN_TARGETS_GENETICS_2                               |     13 |     293 |  4,129,628,057 | 🟡 Medium   |
| OPENAQ                                                |     33 |     891 |  2,443,320,195 | 🟡 Medium   |
| EPA_HISTORICAL_AIR_QUALITY                            |     32 |     879 |  2,437,725,581 | 🟡 Medium   |
| CMS_DATA                                              |     52 |     865 |  2,181,075,029 | 🟡 Medium   |
| NEW_YORK_PLUS                                         |     43 |     845 |  2,126,642,588 | 🟡 Medium   |
| NEW_YORK_GEO                                          |     38 |     658 |  1,627,689,681 | 🟡 Medium   |
| NEW_YORK                                              |     22 |     483 |  1,627,506,185 | 🟡 Medium   |
| STACKOVERFLOW_PLUS                                    |     24 |     345 |    745,472,735 | 🟡 Medium   |
| PATENTS_USPTO                                         |     46 |     444 |    669,659,537 | 🟡 Medium   |
| STACKOVERFLOW                                         |     16 |     228 |    637,122,277 | 🟡 Medium   |
| SEC_QUARTERLY_FINANCIALS                              |     10 |     138 |    535,426,823 | 🟡 Medium   |
| FHIR_SYNTHEA                                          |     17 |     456 |    433,945,069 | 🟡 Medium   |
| META_KAGGLE                                           |     29 |     237 |    344,683,452 | 🟡 Medium   |
| GEO_OPENSTREETMAP_BOUNDARIES                          |     26 |     261 |    217,321,044 | 🟡 Medium   |
| CRYPTO                                                |     39 |     497 |    158,782,141 | 🟡 Medium   |
| PATENTSVIEW                                           |     59 |     304 |    126,201,879 | 🟡 Medium   |
| SAN_FRANCISCO                                         |      9 |     130 |    118,187,859 | 🟡 Medium   |
| OPEN_TARGETS_PLATFORM_2                               |     29 |     351 |     95,468,766 | 🟡 Medium   |
| OPEN_TARGETS_PLATFORM_1                               |     27 |     332 |     95,374,614 | 🟡 Medium   |
| LIBRARIES_IO                                          |      7 |     163 |     89,106,214 | 🟡 Medium   |
| USDA_NASS_AGRICULTURE                                 |     11 |     439 |     76,997,959 | 🟡 Medium   |
| GOOG_BLOCKCHAIN                                       |      7 |     108 |     57,977,736 | 🟡 Medium   |
| TCGA_HG19_DATA_V0                                     |     33 |     401 |     51,298,241 | 🟡 Medium   |
| ECOMMERCE                                             |     17 |     201 |     45,654,003 | 🟡 Medium   |
| COVID19_OPEN_DATA                                     |      2 |     715 |     44,907,165 | 🟡 Medium   |
| SAN_FRANCISCO_PLUS                                    |     20 |     279 |     43,298,246 | 🟡 Medium   |
| WORLD_BANK                                            |     21 |     313 |     20,148,861 | 🟡 Medium   |
| PANCANCER_ATLAS_1                                     |     10 |     833 |     18,945,946 | 🟡 Medium   |
| NPPES                                                 |     20 |     918 |     14,534,949 | 🟡 Medium   |
| AUSTIN                                                |     10 |     119 |      5,912,689 | 🟡 Medium   |
| NCAA_INSIGHTS                                         |     17 |     565 |      5,791,626 | 🟡 Medium   |
| NCAA_BASKETBALL                                       |     10 |     505 |      5,768,154 | 🟡 Medium   |
| CENSUS_BUREAU_USA                                     |     14 |     132 |      4,566,484 | 🟡 Medium   |
| CENSUS_BUREAU_INTERNATIONAL                           |      8 |     165 |      3,469,833 | 🟡 Medium   |
| MITELMAN                                              |     19 |     165 |      2,930,435 | 🟡 Medium   |
| F1                                                    |     29 |     231 |      1,941,243 | 🟡 Medium   |
| DIMENSIONS_AI_COVID19                                 |      6 |     282 |      1,399,321 | 🟡 Medium   |
| COMPLEX_ORACLE                                        |     10 |     140 |      1,064,608 | 🟡 Medium   |
| WIDE_WORLD_IMPORTERS                                  |     31 |     368 |      1,057,452 | 🟡 Medium   |
| BANK_SALES_TRADING                                    |     19 |     106 |      1,054,949 | 🟡 Medium   |
| NOAA_PORTS                                            |     18 |     401 |        903,330 | 🟡 Medium   |
| CITY_LEGISLATION                                      |     15 |     133 |        792,379 | 🟡 Medium   |
| MLB                                                   |      3 |     306 |        772,725 | 🟡 Medium   |
| GENOMICS_CANNABIS                                     |      7 |     159 |        569,808 | 🟡 Medium   |
| CALIFORNIA_TRAFFIC_COLLISION                          |      4 |     120 |        471,571 | 🟡 Medium   |
| HUMAN_GENOME_VARIANTS                                 |      8 |     202 |        234,739 | 🟡 Medium   |
| EU_SOCCER                                             |      8 |     201 |        222,803 | 🟡 Medium   |
| ECLIPSE_MEGAMOVIE                                     |      7 |     129 |        200,878 | 🟡 Medium   |
| ADVENTUREWORKS                                        |     13 |     120 |        168,686 | 🟡 Medium   |
| _1000_GENOMES                                         |      3 |     114 |         41,771 | 🟡 Medium   |
| ORACLE_SQL                                            |     38 |     116 |          1,029 | 🟡 Medium   |

### 🔴 High Complexity Databases (39 total, >1000 columns)

| Database                                               | Tables | Columns | Est. Rows      | Complexity |
|-------------------------------------------------------|-------:|--------:|---------------:|------------|
| PANCANCER_ATLAS_2                                     |     21 |   1,634 |  8,852,666,073 | 🔴 High     |
| HTAN_1                                                |    200 |   7,030 |  5,819,795,740 | 🔴 High     |
| NEW_YORK_GHCN                                         |    288 |   2,624 |  4,516,559,135 | 🔴 High     |
| GHCN_D                                                |    266 |   2,141 |  2,889,052,950 | 🔴 High     |
| NEW_YORK_NOAA                                         |    119 |   3,571 |  1,801,492,788 | 🔴 High     |
| GNOMAD                                                |     71 |  10,264 |    987,103,251 | 🔴 High     |
| NOAA_DATA_PLUS                                        |    234 |   7,450 |    742,276,079 | 🔴 High     |
| NOAA_DATA                                             |    218 |   7,275 |    742,092,583 | 🔴 High     |
| FEC                                                   |    486 |  71,832 |    551,049,355 | 🔴 High     |
| GITHUB_REPOS_DATE                                     |  5,173 |  46,537 |    528,083,235 | 🔴 High     |
| EBI_CHEMBL                                            |    785 |   5,337 |    522,698,820 | 🔴 High     |
| CPTAC_PDC                                             |     79 |   1,451 |    376,808,796 | 🔴 High     |
| NEW_YORK_CITIBIKE_1                                   |    117 |   3,303 |    233,111,096 | 🔴 High     |
| GEO_OPENSTREETMAP_CENSUS_PLACES                       |     67 |   1,056 |    217,197,254 | 🔴 High     |
| NOAA_GSOD                                             |     97 |   3,088 |    173,986,603 | 🔴 High     |
| TCGA_MITELMAN                                         |    176 |   4,272 |    135,541,478 | 🔴 High     |
| TCGA                                                  |    157 |   4,107 |    132,611,047 | 🔴 High     |
| USFS_FIA                                              |     13 |   1,068 |    100,191,674 | 🔴 High     |
| TCGA_HG38_DATA_V0                                     |     50 |   1,145 |     99,538,340 | 🔴 High     |
| COVID19_OPEN_WORLD_BANK                               |     23 |   1,028 |     65,056,026 | 🔴 High     |
| TCGA_BIOCLIN_V0                                       |     80 |   1,831 |     33,627,152 | 🔴 High     |
| HTAN_2                                                |     94 |   3,428 |     24,926,156 | 🔴 High     |
| COVID19_JHU_WORLD_BANK                                |     25 |   3,770 |     24,413,793 | 🔴 High     |
| BLS                                                   |    143 |  23,193 |     18,207,063 | 🔴 High     |
| GOOGLE_DEI                                            |    140 |  23,123 |     18,024,101 | 🔴 High     |
| COVID19_SYMPTOM_SEARCH                                |      6 |   2,580 |     10,557,796 | 🔴 High     |
| COVID19_USA                                           |    285 |  70,858 |      9,289,501 | 🔴 High     |
| NHTSA_TRAFFIC_FATALITIES_PLUS                         |    123 |   2,738 |      8,982,194 | 🔴 High     |
| NHTSA_TRAFFIC_FATALITIES                              |    108 |   2,604 |      6,038,588 | 🔴 High     |
| FIREBASE                                              |    114 |   2,148 |      5,700,000 | 🔴 High     |
| IRS_990                                               |     18 |   2,549 |      5,517,314 | 🔴 High     |
| IDC                                                   |     16 |   2,100 |      4,823,128 | 🔴 High     |
| SDOH                                                  |    294 |  68,863 |      4,417,166 | 🔴 High     |
| CENSUS_BUREAU_ACS_1                                   |    351 |  69,170 |      4,414,432 | 🔴 High     |
| GA4                                                   |     92 |   2,116 |      4,295,584 | 🔴 High     |
| CENSUS_BUREAU_ACS_2                                   |    296 |  68,434 |      4,267,221 | 🔴 High     |
| FDA                                                   |     83 |   1,189 |        981,978 | 🔴 High     |
| GA360                                                 |    366 |   5,522 |        903,653 | 🔴 High     |
| AMAZON_VENDOR_ANALYTICS__SAMPLE_DATASET               |     43 |   1,237 |        567,783 | 🔴 High     |


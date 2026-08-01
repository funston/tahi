# Octo Spider Full Baseline Report

## Interpretation

This report should not be read as a comparison between OCTO and grammar-based SQL generation. Those systems solve different parts of the problem.

- Grammar-based or constrained SQL generation helps with validity: legal syntax, bounded query forms, and fewer parser failures.
- OCTO's intended role is semantic grounding: schema understanding, candidate table and join-path selection, metadata-aware disambiguation, search-space reduction, candidate reranking, and execution-guided repair.

For Spider-style benchmarks, the right target architecture is therefore a hybrid:

1. OCTO builds a task-specific world-model packet for the active database.
2. A cheap SQL model or constrained decoder generates multiple legal candidates.
3. OCTO reranks and repairs those candidates using schema fit, metadata, provenance, and runtime feedback.
4. Final correctness is measured only after execution.

The baseline sections below are useful because they show what happens when the system is missing one of those pieces. A handcrafted or grammar-like path can produce valid SQL without broad semantic coverage. A coprocessor-only heuristic path can retrieve and rank schema context but still fail to synthesize correct SQL at benchmark scale. The actionable lesson is that OCTO should augment a candidate generator, not pretend syntax alone or heuristics alone are enough.

## spider-lite-sql

- Source: `.tmp_spider_lite_full_baseline_current.json`
- Total tasks: 547
- Solved: 12
- Wrong: 0
- Broken: 535
- Indeterminate: 0

| Database | Total | Solved | Wrong | Broken | Indeterminate |
|---|---:|---:|---:|---:|---:|
| SQLITE-SAKILA | 7 | 7 | 0 | 0 | 0 |
| CHINOOK | 3 | 3 | 0 | 0 | 0 |
| PAGILA | 2 | 2 | 0 | 0 | 0 |
| CRYPTO | 20 | 0 | 0 | 20 | 0 |
| THELOOK_ECOMMERCE | 19 | 0 | 0 | 19 | 0 |
| GA4 | 17 | 0 | 0 | 17 | 0 |
| BANK_SALES_TRADING | 15 | 0 | 0 | 15 | 0 |
| GITHUB_REPOS | 15 | 0 | 0 | 15 | 0 |
| IDC | 15 | 0 | 0 | 15 | 0 |
| PATENTS | 15 | 0 | 0 | 15 | 0 |
| STACKOVERFLOW | 15 | 0 | 0 | 15 | 0 |
| GA360 | 12 | 0 | 0 | 12 | 0 |
| NOAA_DATA | 12 | 0 | 0 | 12 | 0 |
| IPL | 11 | 0 | 0 | 11 | 0 |
| CITY_LEGISLATION | 10 | 0 | 0 | 10 | 0 |
| F1 | 9 | 0 | 0 | 9 | 0 |
| FIREBASE | 9 | 0 | 0 | 9 | 0 |
| BRAZILIAN_E_COMMERCE | 8 | 0 | 0 | 8 | 0 |
| ORACLE_SQL | 8 | 0 | 0 | 8 | 0 |
| CMS_DATA | 7 | 0 | 0 | 7 | 0 |
| MODERN_DATA | 7 | 0 | 0 | 7 | 0 |
| SDOH | 7 | 0 | 0 | 7 | 0 |
| COMPLEX_ORACLE | 6 | 0 | 0 | 6 | 0 |
| GEO_OPENSTREETMAP | 6 | 0 | 0 | 6 | 0 |
| GITHUB_REPOS_DATE | 6 | 0 | 0 | 6 | 0 |
| NEW_YORK_PLUS | 6 | 0 | 0 | 6 | 0 |
| PANCANCER_ATLAS_1 | 6 | 0 | 0 | 6 | 0 |
| SAN_FRANCISCO_PLUS | 6 | 0 | 0 | 6 | 0 |
| WORLD_BANK | 6 | 0 | 0 | 6 | 0 |
| AUSTIN | 5 | 0 | 0 | 5 | 0 |
| CHICAGO | 5 | 0 | 0 | 5 | 0 |
| DB-IMDB | 5 | 0 | 0 | 5 | 0 |
| EDUCATION_BUSINESS | 5 | 0 | 0 | 5 | 0 |
| EU_SOCCER | 5 | 0 | 0 | 5 | 0 |
| FDA | 5 | 0 | 0 | 5 | 0 |
| LOG | 5 | 0 | 0 | 5 | 0 |
| META_KAGGLE | 5 | 0 | 0 | 5 | 0 |
| NCAA_BASKETBALL | 5 | 0 | 0 | 5 | 0 |
| CENSUS_BUREAU_ACS_2 | 4 | 0 | 0 | 4 | 0 |
| DEPS_DEV_V1 | 4 | 0 | 0 | 4 | 0 |
| GOOG_BLOCKCHAIN | 4 | 0 | 0 | 4 | 0 |
| NEW_YORK | 4 | 0 | 0 | 4 | 0 |
| NHTSA_TRAFFIC_FATALITIES | 4 | 0 | 0 | 4 | 0 |
| PATENTS_GOOGLE | 4 | 0 | 0 | 4 | 0 |
| TCGA | 4 | 0 | 0 | 4 | 0 |
| TCGA_MITELMAN | 4 | 0 | 0 | 4 | 0 |
| WIDE_WORLD_IMPORTERS | 4 | 0 | 0 | 4 | 0 |
| _1000_GENOMES | 4 | 0 | 0 | 4 | 0 |
| CALIFORNIA_TRAFFIC_COLLISION | 3 | 0 | 0 | 3 | 0 |
| CENSUS_BUREAU_ACS_1 | 3 | 0 | 0 | 3 | 0 |
| CENSUS_BUREAU_INTERNATIONAL | 3 | 0 | 0 | 3 | 0 |
| DELIVERY_CENTER | 3 | 0 | 0 | 3 | 0 |
| ENTERTAINMENTAGENCY | 3 | 0 | 0 | 3 | 0 |
| ETHEREUM_BLOCKCHAIN | 3 | 0 | 0 | 3 | 0 |
| E_COMMERCE | 3 | 0 | 0 | 3 | 0 |
| FINANCE__ECONOMICS | 3 | 0 | 0 | 3 | 0 |
| GNOMAD | 3 | 0 | 0 | 3 | 0 |
| GOOGLE_DEI | 3 | 0 | 0 | 3 | 0 |
| IOWA_LIQUOR_SALES | 3 | 0 | 0 | 3 | 0 |
| LONDON | 3 | 0 | 0 | 3 | 0 |
| MITELMAN | 3 | 0 | 0 | 3 | 0 |
| NEW_YORK_CITIBIKE_1 | 3 | 0 | 0 | 3 | 0 |
| NEW_YORK_NOAA | 3 | 0 | 0 | 3 | 0 |
| OPEN_TARGETS_PLATFORM_1 | 3 | 0 | 0 | 3 | 0 |
| PATENTSVIEW | 3 | 0 | 0 | 3 | 0 |
| STACKING | 3 | 0 | 0 | 3 | 0 |
| TCGA_HG38_DATA_V0 | 3 | 0 | 0 | 3 | 0 |
| THE_MET | 3 | 0 | 0 | 3 | 0 |
| USFS_FIA | 3 | 0 | 0 | 3 | 0 |
| US_REAL_ESTATE | 3 | 0 | 0 | 3 | 0 |
| WORD_VECTORS_US | 3 | 0 | 0 | 3 | 0 |
| AIRLINES | 2 | 0 | 0 | 2 | 0 |
| BASEBALL | 2 | 0 | 0 | 2 | 0 |
| BLS | 2 | 0 | 0 | 2 | 0 |
| BRAZE_USER_EVENT_DEMO_DATASET | 2 | 0 | 0 | 2 | 0 |
| COVID19_OPEN_DATA | 2 | 0 | 0 | 2 | 0 |
| COVID19_SYMPTOM_SEARCH | 2 | 0 | 0 | 2 | 0 |
| COVID19_USA | 2 | 0 | 0 | 2 | 0 |
| CYMBAL_INVESTMENTS | 2 | 0 | 0 | 2 | 0 |
| DEATH | 2 | 0 | 0 | 2 | 0 |
| EBI_CHEMBL | 2 | 0 | 0 | 2 | 0 |
| ECOMMERCE | 2 | 0 | 0 | 2 | 0 |
| FEC | 2 | 0 | 0 | 2 | 0 |
| FHIR_SYNTHEA | 2 | 0 | 0 | 2 | 0 |
| GENOMICS_CANNABIS | 2 | 0 | 0 | 2 | 0 |
| GHCN_D | 2 | 0 | 0 | 2 | 0 |
| GOOGLE_ADS | 2 | 0 | 0 | 2 | 0 |
| GOOGLE_TRENDS | 2 | 0 | 0 | 2 | 0 |
| HTAN_2 | 2 | 0 | 0 | 2 | 0 |
| HUMAN_GENOME_VARIANTS | 2 | 0 | 0 | 2 | 0 |
| IMDB_MOVIES | 2 | 0 | 0 | 2 | 0 |
| NETHERLANDS_OPEN_MAP_DATA | 2 | 0 | 0 | 2 | 0 |
| NOAA_DATA_PLUS | 2 | 0 | 0 | 2 | 0 |
| NOAA_PORTS | 2 | 0 | 0 | 2 | 0 |
| NORTHWIND | 2 | 0 | 0 | 2 | 0 |
| PANCANCER_ATLAS_2 | 2 | 0 | 0 | 2 | 0 |
| PATENTS_USPTO | 2 | 0 | 0 | 2 | 0 |
| SAN_FRANCISCO | 2 | 0 | 0 | 2 | 0 |
| ADVENTUREWORKS | 1 | 0 | 0 | 1 | 0 |
| AMAZON_VENDOR_ANALYTICS__SAMPLE_DATASET | 1 | 0 | 0 | 1 | 0 |
| BBC | 1 | 0 | 0 | 1 | 0 |
| BOWLINGLEAGUE | 1 | 0 | 0 | 1 | 0 |
| CENSUS_BUREAU_USA | 1 | 0 | 0 | 1 | 0 |
| CENSUS_GALAXY__AIML_MODEL_DATA_ENRICHMENT_SAMPLE | 1 | 0 | 0 | 1 | 0 |
| CENSUS_GALAXY__ZIP_CODE_TO_BLOCK_GROUP_SAMPLE | 1 | 0 | 0 | 1 | 0 |
| COVID19_JHU_WORLD_BANK | 1 | 0 | 0 | 1 | 0 |
| COVID19_NYT | 1 | 0 | 0 | 1 | 0 |
| COVID19_OPEN_WORLD_BANK | 1 | 0 | 0 | 1 | 0 |
| CPTAC_PDC | 1 | 0 | 0 | 1 | 0 |
| DIMENSIONS_AI_COVID19 | 1 | 0 | 0 | 1 | 0 |
| ECLIPSE_MEGAMOVIE | 1 | 0 | 0 | 1 | 0 |
| ELECTRONIC_SALES | 1 | 0 | 0 | 1 | 0 |
| EPA_HISTORICAL_AIR_QUALITY | 1 | 0 | 0 | 1 | 0 |
| GBIF | 1 | 0 | 0 | 1 | 0 |
| GEO_OPENSTREETMAP_BOUNDARIES | 1 | 0 | 0 | 1 | 0 |
| GEO_OPENSTREETMAP_CENSUS_PLACES | 1 | 0 | 0 | 1 | 0 |
| GEO_OPENSTREETMAP_WORLDPOP | 1 | 0 | 0 | 1 | 0 |
| GLOBAL_GOVERNMENT | 1 | 0 | 0 | 1 | 0 |
| GLOBAL_WEATHER__CLIMATE_DATA_FOR_BI | 1 | 0 | 0 | 1 | 0 |
| HACKER_NEWS | 1 | 0 | 0 | 1 | 0 |
| HTAN_1 | 1 | 0 | 0 | 1 | 0 |
| IOWA_LIQUOR_SALES_PLUS | 1 | 0 | 0 | 1 | 0 |
| IRS_990 | 1 | 0 | 0 | 1 | 0 |
| LIBRARIES_IO | 1 | 0 | 0 | 1 | 0 |
| MLB | 1 | 0 | 0 | 1 | 0 |
| MUSIC | 1 | 0 | 0 | 1 | 0 |
| NCAA_INSIGHTS | 1 | 0 | 0 | 1 | 0 |
| NEW_YORK_GEO | 1 | 0 | 0 | 1 | 0 |
| NEW_YORK_GHCN | 1 | 0 | 0 | 1 | 0 |
| NHTSA_TRAFFIC_FATALITIES_PLUS | 1 | 0 | 0 | 1 | 0 |
| NOAA_GLOBAL_FORECAST_SYSTEM | 1 | 0 | 0 | 1 | 0 |
| NOAA_GSOD | 1 | 0 | 0 | 1 | 0 |
| NPPES | 1 | 0 | 0 | 1 | 0 |
| OPENAQ | 1 | 0 | 0 | 1 | 0 |
| OPEN_IMAGES | 1 | 0 | 0 | 1 | 0 |
| OPEN_TARGETS_GENETICS_1 | 1 | 0 | 0 | 1 | 0 |
| OPEN_TARGETS_GENETICS_2 | 1 | 0 | 0 | 1 | 0 |
| OPEN_TARGETS_PLATFORM_2 | 1 | 0 | 0 | 1 | 0 |
| PYPI | 1 | 0 | 0 | 1 | 0 |
| SCHOOL_SCHEDULING | 1 | 0 | 0 | 1 | 0 |
| SEC_QUARTERLY_FINANCIALS | 1 | 0 | 0 | 1 | 0 |
| STACKOVERFLOW_PLUS | 1 | 0 | 0 | 1 | 0 |
| SUNROOF_SOLAR | 1 | 0 | 0 | 1 | 0 |
| TARGETOME_REACTOME | 1 | 0 | 0 | 1 | 0 |
| TCGA_BIOCLIN_V0 | 1 | 0 | 0 | 1 | 0 |
| TCGA_HG19_DATA_V0 | 1 | 0 | 0 | 1 | 0 |
| USA_NAMES | 1 | 0 | 0 | 1 | 0 |
| USDA_NASS_AGRICULTURE | 1 | 0 | 0 | 1 | 0 |
| US_ADDRESSES__POI | 1 | 0 | 0 | 1 | 0 |
| WEATHER__ENVIRONMENT | 1 | 0 | 0 | 1 | 0 |
| WWE | 1 | 0 | 0 | 1 | 0 |
| YES_ENERGY__SAMPLE_DATA | 1 | 0 | 0 | 1 | 0 |

Top error signatures:
- 20x `'No schema snapshot registered for db_id=CRYPTO'`
- 19x `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- 17x `'No schema snapshot registered for db_id=ga4'`
- 15x `'No schema snapshot registered for db_id=bank_sales_trading'`
- 15x `'No schema snapshot registered for db_id=PATENTS'`
- 15x `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- 15x `'No schema snapshot registered for db_id=IDC'`
- 13x `'No schema snapshot registered for db_id=stackoverflow'`
- 12x `'No schema snapshot registered for db_id=ga360'`
- 11x `'No schema snapshot registered for db_id=noaa_data'`
- 11x `'No schema snapshot registered for db_id=IPL'`
- 10x `'No schema snapshot registered for db_id=city_legislation'`
- 9x `'No schema snapshot registered for db_id=firebase'`
- 9x `'No schema snapshot registered for db_id=f1'`
- 8x `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`

Broken task IDs:
- `bq001` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `bq002` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `bq003` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `bq004` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `bq006` (AUSTIN): `'No schema snapshot registered for db_id=austin'`
- `bq008` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `bq009` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `bq010` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `bq011` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `bq018` (COVID19_OPEN_DATA): `'No schema snapshot registered for db_id=covid19_open_data'`
- `bq019` (CMS_DATA): `'No schema snapshot registered for db_id=cms_data'`
- `bq021` (NEW_YORK): `'No schema snapshot registered for db_id=new_york'`
- `bq022` (CHICAGO): `'No schema snapshot registered for db_id=chicago'`
- `bq023` (FEC): `'No schema snapshot registered for db_id=fec'`
- `bq024` (USFS_FIA): `'No schema snapshot registered for db_id=usfs_fia'`
- `bq025` (CENSUS_BUREAU_INTERNATIONAL): `'No schema snapshot registered for db_id=census_bureau_international'`
- `bq030` (COVID19_OPEN_DATA): `'No schema snapshot registered for db_id=covid19_open_data'`
- `bq031` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `bq032` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `bq034` (GHCN_D): `'No schema snapshot registered for db_id=ghcn_d'`
- `bq035` (SAN_FRANCISCO): `'No schema snapshot registered for db_id=san_francisco'`
- `bq038` (NEW_YORK): `'No schema snapshot registered for db_id=new_york'`
- `bq039` (NEW_YORK_PLUS): `'No schema snapshot registered for db_id=new_york_plus'`
- `bq040` (NEW_YORK_PLUS): `'No schema snapshot registered for db_id=new_york_plus'`
- `bq041` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `bq042` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `bq045` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `bq046` (TCGA_BIOCLIN_V0): `'No schema snapshot registered for db_id=TCGA_bioclin_v0'`
- `bq047` (NEW_YORK_NOAA): `'No schema snapshot registered for db_id=new_york_noaa'`
- `bq048` (NEW_YORK_NOAA): `'No schema snapshot registered for db_id=new_york_noaa'`
- `bq049` (IOWA_LIQUOR_SALES_PLUS): `'No schema snapshot registered for db_id=iowa_liquor_sales_plus'`
- `bq051` (NEW_YORK_GHCN): `'No schema snapshot registered for db_id=new_york_ghcn'`
- `bq053` (NEW_YORK): `'No schema snapshot registered for db_id=new_york'`
- `bq054` (NEW_YORK): `'No schema snapshot registered for db_id=new_york'`
- `bq055` (GOOGLE_DEI): `'No schema snapshot registered for db_id=google_dei'`
- `bq059` (SAN_FRANCISCO_PLUS): `'No schema snapshot registered for db_id=san_francisco_plus'`
- `bq060` (CENSUS_BUREAU_INTERNATIONAL): `'No schema snapshot registered for db_id=census_bureau_international'`
- `bq061` (CENSUS_BUREAU_ACS_1): `'No schema snapshot registered for db_id=census_bureau_acs_1'`
- `bq064` (CENSUS_BUREAU_ACS_1): `'No schema snapshot registered for db_id=census_bureau_acs_1'`
- `bq066` (SDOH): `'No schema snapshot registered for db_id=sdoh'`
- `bq067` (NHTSA_TRAFFIC_FATALITIES): `'No schema snapshot registered for db_id=nhtsa_traffic_fatalities'`
- `bq074` (SDOH): `'No schema snapshot registered for db_id=sdoh'`
- `bq075` (GOOGLE_DEI): `'No schema snapshot registered for db_id=google_dei'`
- `bq076` (CHICAGO): `'No schema snapshot registered for db_id=chicago'`
- `bq077` (CHICAGO): `'No schema snapshot registered for db_id=chicago'`
- `bq079` (USFS_FIA): `'No schema snapshot registered for db_id=usfs_fia'`
- `bq081` (SAN_FRANCISCO_PLUS): `'No schema snapshot registered for db_id=san_francisco_plus'`
- `bq085` (COVID19_JHU_WORLD_BANK): `'No schema snapshot registered for db_id=covid19_jhu_world_bank'`
- `bq086` (COVID19_OPEN_WORLD_BANK): `'No schema snapshot registered for db_id=covid19_open_world_bank'`
- `bq087` (COVID19_SYMPTOM_SEARCH): `'No schema snapshot registered for db_id=covid19_symptom_search'`
- `bq088` (COVID19_SYMPTOM_SEARCH): `'No schema snapshot registered for db_id=covid19_symptom_search'`
- `bq089` (COVID19_USA): `'No schema snapshot registered for db_id=covid19_usa'`
- `bq090` (CYMBAL_INVESTMENTS): `'No schema snapshot registered for db_id=CYMBAL_INVESTMENTS'`
- `bq094` (FEC): `'No schema snapshot registered for db_id=fec'`
- `bq096` (GBIF): `'No schema snapshot registered for db_id=gbif'`
- `bq097` (SDOH): `'No schema snapshot registered for db_id=sdoh'`
- `bq098` (NEW_YORK_PLUS): `'No schema snapshot registered for db_id=new_york_plus'`
- `bq102` (GNOMAD): `'No schema snapshot registered for db_id=gnomAD'`
- `bq103` (GNOMAD): `'No schema snapshot registered for db_id=gnomAD'`
- `bq105` (NHTSA_TRAFFIC_FATALITIES_PLUS): `'No schema snapshot registered for db_id=nhtsa_traffic_fatalities_plus'`
- `bq108` (NHTSA_TRAFFIC_FATALITIES): `'No schema snapshot registered for db_id=nhtsa_traffic_fatalities'`
- `bq109` (OPEN_TARGETS_GENETICS_1): `'No schema snapshot registered for db_id=open_targets_genetics_1'`
- `bq110` (SDOH): `'No schema snapshot registered for db_id=sdoh'`
- `bq111` (MITELMAN): `'No schema snapshot registered for db_id=mitelman'`
- `bq112` (BLS): `'No schema snapshot registered for db_id=bls'`
- `bq113` (BLS): `'No schema snapshot registered for db_id=bls'`
- `bq114` (OPENAQ): `'No schema snapshot registered for db_id=openaq'`
- `bq115` (CENSUS_BUREAU_INTERNATIONAL): `'No schema snapshot registered for db_id=census_bureau_international'`
- `bq116` (SEC_QUARTERLY_FINANCIALS): `'No schema snapshot registered for db_id=sec_quarterly_financials'`
- `bq119` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `bq120` (SDOH): `'No schema snapshot registered for db_id=sdoh'`
- `bq123` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `bq124` (FHIR_SYNTHEA): `'No schema snapshot registered for db_id=fhir_synthea'`
- `bq126` (THE_MET): `'No schema snapshot registered for db_id=the_met'`
- `bq130` (COVID19_NYT): `'No schema snapshot registered for db_id=covid19_nyt'`
- `bq137` (CENSUS_BUREAU_USA): `'No schema snapshot registered for db_id=census_bureau_usa'`
- `bq143` (CPTAC_PDC): `'No schema snapshot registered for db_id=CPTAC_PDC'`
- `bq144` (NCAA_INSIGHTS): `'No schema snapshot registered for db_id=ncaa_insights'`
- `bq151` (PANCANCER_ATLAS_2): `'No schema snapshot registered for db_id=pancancer_atlas_2'`
- `bq161` (PANCANCER_ATLAS_2): `'No schema snapshot registered for db_id=pancancer_atlas_2'`
- `bq162` (HTAN_1): `'No schema snapshot registered for db_id=HTAN_1'`
- `bq165` (MITELMAN): `'No schema snapshot registered for db_id=mitelman'`
- `bq169` (MITELMAN): `'No schema snapshot registered for db_id=mitelman'`
- `bq172` (CMS_DATA): `'No schema snapshot registered for db_id=cms_data'`
- `bq177` (CMS_DATA): `'No schema snapshot registered for db_id=cms_data'`
- `bq181` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `bq185` (NEW_YORK_PLUS): `'No schema snapshot registered for db_id=new_york_plus'`
- `bq186` (SAN_FRANCISCO): `'No schema snapshot registered for db_id=san_francisco'`
- `bq198` (NCAA_BASKETBALL): `'No schema snapshot registered for db_id=ncaa_basketball'`
- `bq199` (IOWA_LIQUOR_SALES): `'No schema snapshot registered for db_id=iowa_liquor_sales'`
- `bq200` (MLB): `'No schema snapshot registered for db_id=mlb'`
- `bq202` (NEW_YORK_PLUS): `'No schema snapshot registered for db_id=new_york_plus'`
- `bq203` (NEW_YORK_PLUS): `'No schema snapshot registered for db_id=new_york_plus'`
- `bq204` (ECLIPSE_MEGAMOVIE): `'No schema snapshot registered for db_id=eclipse_megamovie'`
- `bq208` (NEW_YORK_NOAA): `'No schema snapshot registered for db_id=new_york_noaa'`
- `bq218` (IOWA_LIQUOR_SALES): `'No schema snapshot registered for db_id=iowa_liquor_sales'`
- `bq220` (USFS_FIA): `'No schema snapshot registered for db_id=usfs_fia'`
- `bq227` (LONDON): `'No schema snapshot registered for db_id=london'`
- `bq228` (LONDON): `'No schema snapshot registered for db_id=london'`
- `bq229` (OPEN_IMAGES): `'No schema snapshot registered for db_id=open_images'`
- `bq230` (USDA_NASS_AGRICULTURE): `'No schema snapshot registered for db_id=usda_nass_agriculture'`
- `bq232` (LONDON): `'No schema snapshot registered for db_id=london'`
- `bq234` (CMS_DATA): `'No schema snapshot registered for db_id=cms_data'`
- `bq235` (CMS_DATA): `'No schema snapshot registered for db_id=cms_data'`
- `bq268` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `bq269` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `bq270` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `bq275` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `bq277` (NOAA_PORTS): `'No schema snapshot registered for db_id=noaa_ports'`
- `bq278` (SUNROOF_SOLAR): `'No schema snapshot registered for db_id=sunroof_solar'`
- `bq279` (AUSTIN): `'No schema snapshot registered for db_id=austin'`
- `bq280` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `bq281` (AUSTIN): `'No schema snapshot registered for db_id=austin'`
- `bq282` (AUSTIN): `'No schema snapshot registered for db_id=austin'`
- `bq284` (BBC): `'No schema snapshot registered for db_id=bbc'`
- `bq285` (FDA): `'No schema snapshot registered for db_id=fda'`
- `bq286` (USA_NAMES): `'No schema snapshot registered for db_id=usa_names'`
- `bq287` (FDA): `'No schema snapshot registered for db_id=fda'`
- `bq288` (FDA): `'No schema snapshot registered for db_id=fda'`
- `bq290` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `bq293` (NEW_YORK_GEO): `'No schema snapshot registered for db_id=new_york_geo'`
- `bq300` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `bq301` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `bq302` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `bq303` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `bq304` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `bq305` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `bq306` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `bq308` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `bq309` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `bq310` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `bq326` (WORLD_BANK): `'No schema snapshot registered for db_id=world_bank'`
- `bq327` (WORLD_BANK): `'No schema snapshot registered for db_id=world_bank'`
- `bq328` (WORLD_BANK): `'No schema snapshot registered for db_id=world_bank'`
- `bq330` (FDA): `'No schema snapshot registered for db_id=fda'`
- `bq338` (CENSUS_BUREAU_ACS_1): `'No schema snapshot registered for db_id=census_bureau_acs_1'`
- `bq339` (SAN_FRANCISCO_PLUS): `'No schema snapshot registered for db_id=san_francisco_plus'`
- `bq352` (SDOH): `'No schema snapshot registered for db_id=sdoh'`
- `bq354` (CMS_DATA): `'No schema snapshot registered for db_id=cms_data'`
- `bq355` (CMS_DATA): `'No schema snapshot registered for db_id=cms_data'`
- `bq356` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `bq357` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `bq360` (NPPES): `'No schema snapshot registered for db_id=nppes'`
- `bq362` (CHICAGO): `'No schema snapshot registered for db_id=chicago'`
- `bq363` (CHICAGO): `'No schema snapshot registered for db_id=chicago'`
- `bq366` (THE_MET): `'No schema snapshot registered for db_id=the_met'`
- `bq374` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `bq376` (SAN_FRANCISCO_PLUS): `'No schema snapshot registered for db_id=san_francisco_plus'`
- `bq383` (GHCN_D): `'No schema snapshot registered for db_id=ghcn_d'`
- `bq389` (EPA_HISTORICAL_AIR_QUALITY): `'No schema snapshot registered for db_id=epa_historical_air_quality'`
- `bq391` (FHIR_SYNTHEA): `'No schema snapshot registered for db_id=fhir_synthea'`
- `bq392` (NOAA_GSOD): `'No schema snapshot registered for db_id=noaa_gsod'`
- `bq393` (HACKER_NEWS): `'No schema snapshot registered for db_id=hacker_news'`
- `bq394` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `bq395` (SDOH): `'No schema snapshot registered for db_id=sdoh'`
- `bq396` (NHTSA_TRAFFIC_FATALITIES): `'No schema snapshot registered for db_id=nhtsa_traffic_fatalities'`
- `bq397` (ECOMMERCE): `'No schema snapshot registered for db_id=ecommerce'`
- `bq398` (WORLD_BANK): `'No schema snapshot registered for db_id=world_bank'`
- `bq399` (WORLD_BANK): `'No schema snapshot registered for db_id=world_bank'`
- `bq400` (SAN_FRANCISCO_PLUS): `'No schema snapshot registered for db_id=san_francisco_plus'`
- `bq402` (ECOMMERCE): `'No schema snapshot registered for db_id=ecommerce'`
- `bq403` (IRS_990): `'No schema snapshot registered for db_id=irs_990'`
- `bq406` (GOOGLE_DEI): `'No schema snapshot registered for db_id=google_dei'`
- `bq407` (COVID19_USA): `'No schema snapshot registered for db_id=covid19_usa'`
- `bq413` (DIMENSIONS_AI_COVID19): `'No schema snapshot registered for db_id=dimensions_ai_covid19'`
- `bq414` (THE_MET): `'No schema snapshot registered for db_id=the_met'`
- `bq418` (TARGETOME_REACTOME): `'No schema snapshot registered for db_id=targetome_reactome'`
- `bq419` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `bq424` (WORLD_BANK): `'No schema snapshot registered for db_id=world_bank'`
- `bq425` (EBI_CHEMBL): `'No schema snapshot registered for db_id=ebi_chembl'`
- `bq427` (NCAA_BASKETBALL): `'No schema snapshot registered for db_id=ncaa_basketball'`
- `bq428` (NCAA_BASKETBALL): `'No schema snapshot registered for db_id=ncaa_basketball'`
- `bq430` (EBI_CHEMBL): `'No schema snapshot registered for db_id=ebi_chembl'`
- `bq432` (FDA): `'No schema snapshot registered for db_id=fda'`
- `bq441` (NHTSA_TRAFFIC_FATALITIES): `'No schema snapshot registered for db_id=nhtsa_traffic_fatalities'`
- `bq442` (CYMBAL_INVESTMENTS): `'No schema snapshot registered for db_id=CYMBAL_INVESTMENTS'`
- `bq445` (GNOMAD): `'No schema snapshot registered for db_id=gnomAD'`
- `bq457` (LIBRARIES_IO): `'No schema snapshot registered for db_id=libraries_io'`
- `bq461` (NCAA_BASKETBALL): `'No schema snapshot registered for db_id=ncaa_basketball'`
- `bq462` (NCAA_BASKETBALL): `'No schema snapshot registered for db_id=ncaa_basketball'`
- `ga001` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `ga002` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `ga003` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `ga004` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `ga005` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `ga006` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `ga007` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `ga008` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `ga009` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `ga010` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `ga011` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `ga012` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `ga013` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `ga014` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `ga017` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `ga018` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `ga019` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `ga020` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `ga021` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `ga022` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `ga025` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `ga028` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `ga030` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `ga031` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `ga032` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `local002` (E_COMMERCE): `'No schema snapshot registered for db_id=E_commerce'`
- `local003` (E_COMMERCE): `'No schema snapshot registered for db_id=E_commerce'`
- `local004` (E_COMMERCE): `'No schema snapshot registered for db_id=E_commerce'`
- `local007` (BASEBALL): `'No schema snapshot registered for db_id=Baseball'`
- `local008` (BASEBALL): `'No schema snapshot registered for db_id=Baseball'`
- `local009` (AIRLINES): `'No schema snapshot registered for db_id=Airlines'`
- `local010` (AIRLINES): `'No schema snapshot registered for db_id=Airlines'`
- `local015` (CALIFORNIA_TRAFFIC_COLLISION): `'No schema snapshot registered for db_id=California_Traffic_Collision'`
- `local017` (CALIFORNIA_TRAFFIC_COLLISION): `'No schema snapshot registered for db_id=California_Traffic_Collision'`
- `local018` (CALIFORNIA_TRAFFIC_COLLISION): `'No schema snapshot registered for db_id=California_Traffic_Collision'`
- `local019` (WWE): `'No schema snapshot registered for db_id=WWE'`
- `local020` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `local021` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `local022` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `local023` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `local024` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `local025` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `local026` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `local028` (BRAZILIAN_E_COMMERCE): `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`
- `local029` (BRAZILIAN_E_COMMERCE): `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`
- `local030` (BRAZILIAN_E_COMMERCE): `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`
- `local031` (BRAZILIAN_E_COMMERCE): `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`
- `local032` (BRAZILIAN_E_COMMERCE): `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`
- `local034` (BRAZILIAN_E_COMMERCE): `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`
- `local035` (BRAZILIAN_E_COMMERCE): `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`
- `local037` (BRAZILIAN_E_COMMERCE): `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`
- `local040` (MODERN_DATA): `'No schema snapshot registered for db_id=modern_data'`
- `local041` (MODERN_DATA): `'No schema snapshot registered for db_id=modern_data'`
- `local049` (MODERN_DATA): `'No schema snapshot registered for db_id=modern_data'`
- `local050` (COMPLEX_ORACLE): `'No schema snapshot registered for db_id=complex_oracle'`
- `local058` (EDUCATION_BUSINESS): `'No schema snapshot registered for db_id=education_business'`
- `local059` (EDUCATION_BUSINESS): `'No schema snapshot registered for db_id=education_business'`
- `local060` (COMPLEX_ORACLE): `'No schema snapshot registered for db_id=complex_oracle'`
- `local061` (COMPLEX_ORACLE): `'No schema snapshot registered for db_id=complex_oracle'`
- `local062` (COMPLEX_ORACLE): `'No schema snapshot registered for db_id=complex_oracle'`
- `local063` (COMPLEX_ORACLE): `'No schema snapshot registered for db_id=complex_oracle'`
- `local064` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `local065` (MODERN_DATA): `'No schema snapshot registered for db_id=modern_data'`
- `local066` (MODERN_DATA): `'No schema snapshot registered for db_id=modern_data'`
- `local067` (COMPLEX_ORACLE): `'No schema snapshot registered for db_id=complex_oracle'`
- `local068` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `local070` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `local071` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `local072` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `local073` (MODERN_DATA): `'No schema snapshot registered for db_id=modern_data'`
- `local074` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `local075` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `local077` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `local078` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `local081` (NORTHWIND): `'No schema snapshot registered for db_id=northwind'`
- `local085` (NORTHWIND): `'No schema snapshot registered for db_id=northwind'`
- `local096` (DB-IMDB): `'No schema snapshot registered for db_id=Db-IMDB'`
- `local097` (DB-IMDB): `'No schema snapshot registered for db_id=Db-IMDB'`
- `local098` (DB-IMDB): `'No schema snapshot registered for db_id=Db-IMDB'`
- `local099` (DB-IMDB): `'No schema snapshot registered for db_id=Db-IMDB'`
- `local100` (DB-IMDB): `'No schema snapshot registered for db_id=Db-IMDB'`
- `local114` (EDUCATION_BUSINESS): `'No schema snapshot registered for db_id=education_business'`
- `local128` (BOWLINGLEAGUE): `'No schema snapshot registered for db_id=BowlingLeague'`
- `local130` (SCHOOL_SCHEDULING): `'No schema snapshot registered for db_id=school_scheduling'`
- `local131` (ENTERTAINMENTAGENCY): `'No schema snapshot registered for db_id=EntertainmentAgency'`
- `local132` (ENTERTAINMENTAGENCY): `'No schema snapshot registered for db_id=EntertainmentAgency'`
- `local133` (ENTERTAINMENTAGENCY): `'No schema snapshot registered for db_id=EntertainmentAgency'`
- `local141` (ADVENTUREWORKS): `'No schema snapshot registered for db_id=AdventureWorks'`
- `local152` (IMDB_MOVIES): `'No schema snapshot registered for db_id=imdb_movies'`
- `local156` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `local157` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `local163` (EDUCATION_BUSINESS): `'No schema snapshot registered for db_id=education_business'`
- `local167` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `local168` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `local169` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `local170` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `local171` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `local201` (MODERN_DATA): `'No schema snapshot registered for db_id=modern_data'`
- `local202` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `local209` (DELIVERY_CENTER): `'No schema snapshot registered for db_id=delivery_center'`
- `local210` (DELIVERY_CENTER): `'No schema snapshot registered for db_id=delivery_center'`
- `local212` (DELIVERY_CENTER): `'No schema snapshot registered for db_id=delivery_center'`
- `local218` (EU_SOCCER): `'No schema snapshot registered for db_id=EU_soccer'`
- `local219` (EU_SOCCER): `'No schema snapshot registered for db_id=EU_soccer'`
- `local220` (EU_SOCCER): `'No schema snapshot registered for db_id=EU_soccer'`
- `local221` (EU_SOCCER): `'No schema snapshot registered for db_id=EU_soccer'`
- `local228` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `local229` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `local230` (IMDB_MOVIES): `'No schema snapshot registered for db_id=imdb_movies'`
- `local244` (MUSIC): `'No schema snapshot registered for db_id=music'`
- `local253` (EDUCATION_BUSINESS): `'No schema snapshot registered for db_id=education_business'`
- `local258` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `local259` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `local262` (STACKING): `'No schema snapshot registered for db_id=stacking'`
- `local263` (STACKING): `'No schema snapshot registered for db_id=stacking'`
- `local264` (STACKING): `'No schema snapshot registered for db_id=stacking'`
- `local269` (ORACLE_SQL): `'No schema snapshot registered for db_id=oracle_sql'`
- `local270` (ORACLE_SQL): `'No schema snapshot registered for db_id=oracle_sql'`
- `local272` (ORACLE_SQL): `'No schema snapshot registered for db_id=oracle_sql'`
- `local273` (ORACLE_SQL): `'No schema snapshot registered for db_id=oracle_sql'`
- `local274` (ORACLE_SQL): `'No schema snapshot registered for db_id=oracle_sql'`
- `local275` (ORACLE_SQL): `'No schema snapshot registered for db_id=oracle_sql'`
- `local277` (ORACLE_SQL): `'No schema snapshot registered for db_id=oracle_sql'`
- `local279` (ORACLE_SQL): `'No schema snapshot registered for db_id=oracle_sql'`
- `local283` (EU_SOCCER): `'No schema snapshot registered for db_id=EU_soccer'`
- `local284` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `local285` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `local286` (ELECTRONIC_SALES): `'No schema snapshot registered for db_id=electronic_sales'`
- `local297` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `local298` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `local299` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `local300` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `local301` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `local302` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `local309` (F1): `'No schema snapshot registered for db_id=f1'`
- `local310` (F1): `'No schema snapshot registered for db_id=f1'`
- `local311` (F1): `'No schema snapshot registered for db_id=f1'`
- `local329` (LOG): `'No schema snapshot registered for db_id=log'`
- `local330` (LOG): `'No schema snapshot registered for db_id=log'`
- `local331` (LOG): `'No schema snapshot registered for db_id=log'`
- `local335` (F1): `'No schema snapshot registered for db_id=f1'`
- `local336` (F1): `'No schema snapshot registered for db_id=f1'`
- `local344` (F1): `'No schema snapshot registered for db_id=f1'`
- `local354` (F1): `'No schema snapshot registered for db_id=f1'`
- `local355` (F1): `'No schema snapshot registered for db_id=f1'`
- `local356` (F1): `'No schema snapshot registered for db_id=f1'`
- `local358` (LOG): `'No schema snapshot registered for db_id=log'`
- `local360` (LOG): `'No schema snapshot registered for db_id=log'`
- `sf001` (GLOBAL_WEATHER__CLIMATE_DATA_FOR_BI): `'No schema snapshot registered for db_id=GLOBAL_WEATHER__CLIMATE_DATA_FOR_BI'`
- `sf002` (FINANCE__ECONOMICS): `'No schema snapshot registered for db_id=FINANCE__ECONOMICS'`
- `sf003` (GLOBAL_GOVERNMENT): `'No schema snapshot registered for db_id=GLOBAL_GOVERNMENT'`
- `sf006` (FINANCE__ECONOMICS): `'No schema snapshot registered for db_id=FINANCE__ECONOMICS'`
- `sf008` (US_REAL_ESTATE): `'No schema snapshot registered for db_id=US_REAL_ESTATE'`
- `sf009` (NETHERLANDS_OPEN_MAP_DATA): `'No schema snapshot registered for db_id=NETHERLANDS_OPEN_MAP_DATA'`
- `sf010` (US_REAL_ESTATE): `'No schema snapshot registered for db_id=US_REAL_ESTATE'`
- `sf011` (CENSUS_GALAXY__ZIP_CODE_TO_BLOCK_GROUP_SAMPLE): `'No schema snapshot registered for db_id=CENSUS_GALAXY__ZIP_CODE_TO_BLOCK_GROUP_SAMPLE'`
- `sf012` (WEATHER__ENVIRONMENT): `'No schema snapshot registered for db_id=WEATHER__ENVIRONMENT'`
- `sf013` (NETHERLANDS_OPEN_MAP_DATA): `'No schema snapshot registered for db_id=NETHERLANDS_OPEN_MAP_DATA'`
- `sf014` (CENSUS_GALAXY__AIML_MODEL_DATA_ENRICHMENT_SAMPLE): `'No schema snapshot registered for db_id=CENSUS_GALAXY__AIML_MODEL_DATA_ENRICHMENT_SAMPLE'`
- `sf018` (BRAZE_USER_EVENT_DEMO_DATASET): `'No schema snapshot registered for db_id=BRAZE_USER_EVENT_DEMO_DATASET'`
- `sf029` (AMAZON_VENDOR_ANALYTICS__SAMPLE_DATASET): `'No schema snapshot registered for db_id=AMAZON_VENDOR_ANALYTICS__SAMPLE_DATASET'`
- `sf035` (BRAZE_USER_EVENT_DEMO_DATASET): `'No schema snapshot registered for db_id=BRAZE_USER_EVENT_DEMO_DATASET'`
- `sf037` (US_REAL_ESTATE): `'No schema snapshot registered for db_id=US_REAL_ESTATE'`
- `sf040` (US_ADDRESSES__POI): `'No schema snapshot registered for db_id=US_ADDRESSES__POI'`
- `sf041` (YES_ENERGY__SAMPLE_DATA): `'No schema snapshot registered for db_id=YES_ENERGY__SAMPLE_DATA'`
- `sf044` (FINANCE__ECONOMICS): `'No schema snapshot registered for db_id=FINANCE__ECONOMICS'`
- `sf_bq005` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq007` (CENSUS_BUREAU_ACS_2): `'No schema snapshot registered for db_id=CENSUS_BUREAU_ACS_2'`
- `sf_bq012` (ETHEREUM_BLOCKCHAIN): `'No schema snapshot registered for db_id=ETHEREUM_BLOCKCHAIN'`
- `sf_bq014` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq015` (STACKOVERFLOW_PLUS): `'No schema snapshot registered for db_id=STACKOVERFLOW_PLUS'`
- `sf_bq016` (DEPS_DEV_V1): `'No schema snapshot registered for db_id=DEPS_DEV_V1'`
- `sf_bq017` (GEO_OPENSTREETMAP): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP'`
- `sf_bq020` (GENOMICS_CANNABIS): `'No schema snapshot registered for db_id=GENOMICS_CANNABIS'`
- `sf_bq026` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `sf_bq027` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `sf_bq028` (DEPS_DEV_V1): `'No schema snapshot registered for db_id=DEPS_DEV_V1'`
- `sf_bq029` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `sf_bq033` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `sf_bq036` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `sf_bq037` (HUMAN_GENOME_VARIANTS): `'No schema snapshot registered for db_id=HUMAN_GENOME_VARIANTS'`
- `sf_bq043` (TCGA): `'No schema snapshot registered for db_id=TCGA'`
- `sf_bq044` (TCGA): `'No schema snapshot registered for db_id=TCGA'`
- `sf_bq050` (NEW_YORK_CITIBIKE_1): `'No schema snapshot registered for db_id=NEW_YORK_CITIBIKE_1'`
- `sf_bq052` (PATENTSVIEW): `'No schema snapshot registered for db_id=PATENTSVIEW'`
- `sf_bq056` (GEO_OPENSTREETMAP_BOUNDARIES): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP_BOUNDARIES'`
- `sf_bq057` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq058` (GOOG_BLOCKCHAIN): `'No schema snapshot registered for db_id=GOOG_BLOCKCHAIN'`
- `sf_bq062` (DEPS_DEV_V1): `'No schema snapshot registered for db_id=DEPS_DEV_V1'`
- `sf_bq063` (DEPS_DEV_V1): `'No schema snapshot registered for db_id=DEPS_DEV_V1'`
- `sf_bq065` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq068` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq069` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `sf_bq070` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `sf_bq071` (NOAA_DATA_PLUS): `'No schema snapshot registered for db_id=NOAA_DATA_PLUS'`
- `sf_bq072` (DEATH): `'No schema snapshot registered for db_id=DEATH'`
- `sf_bq073` (CENSUS_BUREAU_ACS_2): `'No schema snapshot registered for db_id=CENSUS_BUREAU_ACS_2'`
- `sf_bq078` (OPEN_TARGETS_PLATFORM_2): `'No schema snapshot registered for db_id=OPEN_TARGETS_PLATFORM_2'`
- `sf_bq080` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq083` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq084` (GOOG_BLOCKCHAIN): `'No schema snapshot registered for db_id=GOOG_BLOCKCHAIN'`
- `sf_bq091` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `sf_bq092` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq093` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq095` (OPEN_TARGETS_PLATFORM_1): `'No schema snapshot registered for db_id=OPEN_TARGETS_PLATFORM_1'`
- `sf_bq099` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `sf_bq100` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `sf_bq101` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `sf_bq104` (GOOGLE_TRENDS): `'No schema snapshot registered for db_id=GOOGLE_TRENDS'`
- `sf_bq107` (GENOMICS_CANNABIS): `'No schema snapshot registered for db_id=GENOMICS_CANNABIS'`
- `sf_bq117` (NOAA_DATA): `'No schema snapshot registered for db_id=NOAA_DATA'`
- `sf_bq118` (DEATH): `'No schema snapshot registered for db_id=DEATH'`
- `sf_bq121` (STACKOVERFLOW): `'No schema snapshot registered for db_id=STACKOVERFLOW'`
- `sf_bq127` (PATENTS_GOOGLE): `'No schema snapshot registered for db_id=PATENTS_GOOGLE'`
- `sf_bq128` (PATENTSVIEW): `'No schema snapshot registered for db_id=PATENTSVIEW'`
- `sf_bq131` (GEO_OPENSTREETMAP): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP'`
- `sf_bq135` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq136` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq141` (TCGA_HG38_DATA_V0): `'No schema snapshot registered for db_id=TCGA_HG38_DATA_V0'`
- `sf_bq147` (TCGA): `'No schema snapshot registered for db_id=TCGA'`
- `sf_bq148` (TCGA): `'No schema snapshot registered for db_id=TCGA'`
- `sf_bq150` (TCGA_HG19_DATA_V0): `'No schema snapshot registered for db_id=TCGA_HG19_DATA_V0'`
- `sf_bq152` (TCGA_HG38_DATA_V0): `'No schema snapshot registered for db_id=TCGA_HG38_DATA_V0'`
- `sf_bq153` (PANCANCER_ATLAS_1): `'No schema snapshot registered for db_id=PANCANCER_ATLAS_1'`
- `sf_bq154` (PANCANCER_ATLAS_1): `'No schema snapshot registered for db_id=PANCANCER_ATLAS_1'`
- `sf_bq155` (TCGA_HG38_DATA_V0): `'No schema snapshot registered for db_id=TCGA_HG38_DATA_V0'`
- `sf_bq156` (PANCANCER_ATLAS_1): `'No schema snapshot registered for db_id=PANCANCER_ATLAS_1'`
- `sf_bq157` (PANCANCER_ATLAS_1): `'No schema snapshot registered for db_id=PANCANCER_ATLAS_1'`
- `sf_bq158` (PANCANCER_ATLAS_1): `'No schema snapshot registered for db_id=PANCANCER_ATLAS_1'`
- `sf_bq159` (PANCANCER_ATLAS_1): `'No schema snapshot registered for db_id=PANCANCER_ATLAS_1'`
- `sf_bq160` (META_KAGGLE): `'No schema snapshot registered for db_id=META_KAGGLE'`
- `sf_bq163` (HTAN_2): `'No schema snapshot registered for db_id=HTAN_2'`
- `sf_bq164` (HTAN_2): `'No schema snapshot registered for db_id=HTAN_2'`
- `sf_bq166` (TCGA_MITELMAN): `'No schema snapshot registered for db_id=TCGA_MITELMAN'`
- `sf_bq167` (META_KAGGLE): `'No schema snapshot registered for db_id=META_KAGGLE'`
- `sf_bq170` (TCGA_MITELMAN): `'No schema snapshot registered for db_id=TCGA_MITELMAN'`
- `sf_bq171` (META_KAGGLE): `'No schema snapshot registered for db_id=META_KAGGLE'`
- `sf_bq175` (TCGA_MITELMAN): `'No schema snapshot registered for db_id=TCGA_MITELMAN'`
- `sf_bq176` (TCGA_MITELMAN): `'No schema snapshot registered for db_id=TCGA_MITELMAN'`
- `sf_bq180` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `sf_bq182` (GITHUB_REPOS_DATE): `'No schema snapshot registered for db_id=GITHUB_REPOS_DATE'`
- `sf_bq184` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq187` (ETHEREUM_BLOCKCHAIN): `'No schema snapshot registered for db_id=ETHEREUM_BLOCKCHAIN'`
- `sf_bq188` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq189` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq190` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq191` (GITHUB_REPOS_DATE): `'No schema snapshot registered for db_id=GITHUB_REPOS_DATE'`
- `sf_bq192` (GITHUB_REPOS_DATE): `'No schema snapshot registered for db_id=GITHUB_REPOS_DATE'`
- `sf_bq193` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `sf_bq194` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `sf_bq195` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq197` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq207` (PATENTS_USPTO): `'No schema snapshot registered for db_id=PATENTS_USPTO'`
- `sf_bq209` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `sf_bq210` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `sf_bq211` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `sf_bq212` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `sf_bq213` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `sf_bq214` (PATENTS_GOOGLE): `'No schema snapshot registered for db_id=PATENTS_GOOGLE'`
- `sf_bq215` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `sf_bq216` (PATENTS_GOOGLE): `'No schema snapshot registered for db_id=PATENTS_GOOGLE'`
- `sf_bq217` (GITHUB_REPOS_DATE): `'No schema snapshot registered for db_id=GITHUB_REPOS_DATE'`
- `sf_bq219` (IOWA_LIQUOR_SALES): `'No schema snapshot registered for db_id=IOWA_LIQUOR_SALES'`
- `sf_bq221` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `sf_bq222` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `sf_bq223` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `sf_bq224` (GITHUB_REPOS_DATE): `'No schema snapshot registered for db_id=GITHUB_REPOS_DATE'`
- `sf_bq225` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `sf_bq226` (GOOG_BLOCKCHAIN): `'No schema snapshot registered for db_id=GOOG_BLOCKCHAIN'`
- `sf_bq233` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `sf_bq236` (NOAA_DATA_PLUS): `'No schema snapshot registered for db_id=NOAA_DATA_PLUS'`
- `sf_bq246` (PATENTSVIEW): `'No schema snapshot registered for db_id=PATENTSVIEW'`
- `sf_bq247` (PATENTS_GOOGLE): `'No schema snapshot registered for db_id=PATENTS_GOOGLE'`
- `sf_bq248` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `sf_bq249` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `sf_bq250` (GEO_OPENSTREETMAP_WORLDPOP): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP_WORLDPOP'`
- `sf_bq251` (PYPI): `'No schema snapshot registered for db_id=PYPI'`
- `sf_bq252` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `sf_bq253` (GEO_OPENSTREETMAP): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP'`
- `sf_bq254` (GEO_OPENSTREETMAP): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP'`
- `sf_bq255` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `sf_bq256` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq258` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq259` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq260` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq261` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq262` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq263` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq264` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq265` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq266` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq271` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq272` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq273` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq276` (NOAA_PORTS): `'No schema snapshot registered for db_id=NOAA_PORTS'`
- `sf_bq283` (AUSTIN): `'No schema snapshot registered for db_id=AUSTIN'`
- `sf_bq289` (GEO_OPENSTREETMAP_CENSUS_PLACES): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP_CENSUS_PLACES'`
- `sf_bq291` (NOAA_GLOBAL_FORECAST_SYSTEM): `'No schema snapshot registered for db_id=NOAA_GLOBAL_FORECAST_SYSTEM'`
- `sf_bq292` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq294` (SAN_FRANCISCO_PLUS): `'No schema snapshot registered for db_id=SAN_FRANCISCO_PLUS'`
- `sf_bq295` (GITHUB_REPOS_DATE): `'No schema snapshot registered for db_id=GITHUB_REPOS_DATE'`
- `sf_bq307` (STACKOVERFLOW): `'No schema snapshot registered for db_id=STACKOVERFLOW'`
- `sf_bq320` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `sf_bq321` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `sf_bq323` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `sf_bq324` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `sf_bq325` (OPEN_TARGETS_GENETICS_2): `'No schema snapshot registered for db_id=OPEN_TARGETS_GENETICS_2'`
- `sf_bq331` (META_KAGGLE): `'No schema snapshot registered for db_id=META_KAGGLE'`
- `sf_bq333` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq334` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq335` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq340` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq341` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq342` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq345` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `sf_bq346` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `sf_bq347` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `sf_bq348` (GEO_OPENSTREETMAP): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP'`
- `sf_bq349` (GEO_OPENSTREETMAP): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP'`
- `sf_bq350` (OPEN_TARGETS_PLATFORM_1): `'No schema snapshot registered for db_id=OPEN_TARGETS_PLATFORM_1'`
- `sf_bq358` (NEW_YORK_CITIBIKE_1): `'No schema snapshot registered for db_id=NEW_YORK_CITIBIKE_1'`
- `sf_bq359` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `sf_bq361` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `sf_bq370` (WIDE_WORLD_IMPORTERS): `'No schema snapshot registered for db_id=WIDE_WORLD_IMPORTERS'`
- `sf_bq371` (WIDE_WORLD_IMPORTERS): `'No schema snapshot registered for db_id=WIDE_WORLD_IMPORTERS'`
- `sf_bq372` (WIDE_WORLD_IMPORTERS): `'No schema snapshot registered for db_id=WIDE_WORLD_IMPORTERS'`
- `sf_bq373` (WIDE_WORLD_IMPORTERS): `'No schema snapshot registered for db_id=WIDE_WORLD_IMPORTERS'`
- `sf_bq375` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `sf_bq377` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `sf_bq379` (OPEN_TARGETS_PLATFORM_1): `'No schema snapshot registered for db_id=OPEN_TARGETS_PLATFORM_1'`
- `sf_bq380` (META_KAGGLE): `'No schema snapshot registered for db_id=META_KAGGLE'`
- `sf_bq390` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `sf_bq410` (CENSUS_BUREAU_ACS_2): `'No schema snapshot registered for db_id=CENSUS_BUREAU_ACS_2'`
- `sf_bq411` (GOOGLE_TRENDS): `'No schema snapshot registered for db_id=GOOGLE_TRENDS'`
- `sf_bq412` (GOOGLE_ADS): `'No schema snapshot registered for db_id=GOOGLE_ADS'`
- `sf_bq415` (HUMAN_GENOME_VARIANTS): `'No schema snapshot registered for db_id=HUMAN_GENOME_VARIANTS'`
- `sf_bq416` (GOOG_BLOCKCHAIN): `'No schema snapshot registered for db_id=GOOG_BLOCKCHAIN'`
- `sf_bq417` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `sf_bq420` (PATENTS_USPTO): `'No schema snapshot registered for db_id=PATENTS_USPTO'`
- `sf_bq421` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `sf_bq422` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `sf_bq423` (GOOGLE_ADS): `'No schema snapshot registered for db_id=GOOGLE_ADS'`
- `sf_bq426` (NEW_YORK_CITIBIKE_1): `'No schema snapshot registered for db_id=NEW_YORK_CITIBIKE_1'`
- `sf_bq429` (CENSUS_BUREAU_ACS_2): `'No schema snapshot registered for db_id=CENSUS_BUREAU_ACS_2'`
- `sf_bq444` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `sf_bq450` (ETHEREUM_BLOCKCHAIN): `'No schema snapshot registered for db_id=ETHEREUM_BLOCKCHAIN'`
- `sf_bq451` (_1000_GENOMES): `'No schema snapshot registered for db_id=_1000_GENOMES'`
- `sf_bq452` (_1000_GENOMES): `'No schema snapshot registered for db_id=_1000_GENOMES'`
- `sf_bq453` (_1000_GENOMES): `'No schema snapshot registered for db_id=_1000_GENOMES'`
- `sf_bq454` (_1000_GENOMES): `'No schema snapshot registered for db_id=_1000_GENOMES'`
- `sf_bq455` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `sf_bq456` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `sf_bq458` (WORD_VECTORS_US): `'No schema snapshot registered for db_id=WORD_VECTORS_US'`
- `sf_bq459` (WORD_VECTORS_US): `'No schema snapshot registered for db_id=WORD_VECTORS_US'`
- `sf_bq460` (WORD_VECTORS_US): `'No schema snapshot registered for db_id=WORD_VECTORS_US'`

Wrong-but-executed task IDs:
- None

## spider-snow-sql

- Source: `.tmp_spider_snow_full_baseline_current.json`
- Total tasks: 547
- Solved: 19
- Wrong: 521
- Broken: 7
- Indeterminate: 0

| Database | Total | Solved | Wrong | Broken | Indeterminate |
|---|---:|---:|---:|---:|---:|
| BRAZILIAN_E_COMMERCE | 8 | 5 | 2 | 1 | 0 |
| CHICAGO | 5 | 5 | 0 | 0 | 0 |
| AUSTIN | 5 | 4 | 1 | 0 | 0 |
| TCGA_MITELMAN | 5 | 3 | 2 | 0 | 0 |
| BBC | 1 | 1 | 0 | 0 | 0 |
| USA_NAMES | 1 | 1 | 0 | 0 | 0 |
| CRYPTO | 20 | 0 | 20 | 0 | 0 |
| THELOOK_ECOMMERCE | 19 | 0 | 19 | 0 | 0 |
| GA4 | 17 | 0 | 17 | 0 | 0 |
| BANK_SALES_TRADING | 15 | 0 | 15 | 0 | 0 |
| GITHUB_REPOS | 15 | 0 | 15 | 0 | 0 |
| IDC | 15 | 0 | 15 | 0 | 0 |
| PATENTS | 15 | 0 | 15 | 0 | 0 |
| STACKOVERFLOW | 15 | 0 | 15 | 0 | 0 |
| GA360 | 12 | 0 | 12 | 0 | 0 |
| NOAA_DATA | 12 | 0 | 12 | 0 | 0 |
| IPL | 11 | 0 | 11 | 0 | 0 |
| CITY_LEGISLATION | 10 | 0 | 10 | 0 | 0 |
| F1 | 9 | 0 | 9 | 0 | 0 |
| FIREBASE | 9 | 0 | 9 | 0 | 0 |
| ORACLE_SQL | 8 | 0 | 8 | 0 | 0 |
| CMS_DATA | 7 | 0 | 7 | 0 | 0 |
| MODERN_DATA | 7 | 0 | 7 | 0 | 0 |
| SDOH | 7 | 0 | 7 | 0 | 0 |
| SQLITE_SAKILA | 7 | 0 | 7 | 0 | 0 |
| COMPLEX_ORACLE | 6 | 0 | 6 | 0 | 0 |
| GEO_OPENSTREETMAP | 6 | 0 | 6 | 0 | 0 |
| GITHUB_REPOS_DATE | 6 | 0 | 6 | 0 | 0 |
| NEW_YORK_PLUS | 6 | 0 | 6 | 0 | 0 |
| PANCANCER_ATLAS_1 | 6 | 0 | 6 | 0 | 0 |
| SAN_FRANCISCO_PLUS | 6 | 0 | 6 | 0 | 0 |
| WORLD_BANK | 6 | 0 | 6 | 0 | 0 |
| DB_IMDB | 5 | 0 | 5 | 0 | 0 |
| EDUCATION_BUSINESS | 5 | 0 | 5 | 0 | 0 |
| EU_SOCCER | 5 | 0 | 5 | 0 | 0 |
| FDA | 5 | 0 | 5 | 0 | 0 |
| LOG | 5 | 0 | 5 | 0 | 0 |
| META_KAGGLE | 5 | 0 | 5 | 0 | 0 |
| NCAA_BASKETBALL | 5 | 0 | 5 | 0 | 0 |
| CENSUS_BUREAU_ACS_2 | 4 | 0 | 4 | 0 | 0 |
| DEPS_DEV_V1 | 4 | 0 | 4 | 0 | 0 |
| GOOG_BLOCKCHAIN | 4 | 0 | 4 | 0 | 0 |
| NEW_YORK | 4 | 0 | 4 | 0 | 0 |
| NHTSA_TRAFFIC_FATALITIES | 4 | 0 | 4 | 0 | 0 |
| PATENTS_GOOGLE | 4 | 0 | 4 | 0 | 0 |
| TCGA | 4 | 0 | 4 | 0 | 0 |
| WIDE_WORLD_IMPORTERS | 4 | 0 | 4 | 0 | 0 |
| _1000_GENOMES | 4 | 0 | 4 | 0 | 0 |
| CALIFORNIA_TRAFFIC_COLLISION | 3 | 0 | 3 | 0 | 0 |
| CENSUS_BUREAU_ACS_1 | 3 | 0 | 3 | 0 | 0 |
| CENSUS_BUREAU_INTERNATIONAL | 3 | 0 | 3 | 0 | 0 |
| CHINOOK | 3 | 0 | 3 | 0 | 0 |
| DELIVERY_CENTER | 3 | 0 | 3 | 0 | 0 |
| ENTERTAINMENTAGENCY | 3 | 0 | 3 | 0 | 0 |
| ETHEREUM_BLOCKCHAIN | 3 | 0 | 3 | 0 | 0 |
| E_COMMERCE | 3 | 0 | 3 | 0 | 0 |
| FINANCE__ECONOMICS | 3 | 0 | 3 | 0 | 0 |
| GNOMAD | 3 | 0 | 3 | 0 | 0 |
| GOOGLE_DEI | 3 | 0 | 3 | 0 | 0 |
| IOWA_LIQUOR_SALES | 3 | 0 | 3 | 0 | 0 |
| LONDON | 3 | 0 | 3 | 0 | 0 |
| NEW_YORK_CITIBIKE_1 | 3 | 0 | 3 | 0 | 0 |
| NEW_YORK_NOAA | 3 | 0 | 3 | 0 | 0 |
| OPEN_TARGETS_PLATFORM_1 | 3 | 0 | 3 | 0 | 0 |
| PATENTSVIEW | 3 | 0 | 3 | 0 | 0 |
| STACKING | 3 | 0 | 3 | 0 | 0 |
| TCGA_HG38_DATA_V0 | 3 | 0 | 3 | 0 | 0 |
| THE_MET | 3 | 0 | 3 | 0 | 0 |
| USFS_FIA | 3 | 0 | 3 | 0 | 0 |
| US_REAL_ESTATE | 3 | 0 | 3 | 0 | 0 |
| WORD_VECTORS_US | 3 | 0 | 3 | 0 | 0 |
| AIRLINES | 2 | 0 | 2 | 0 | 0 |
| BASEBALL | 2 | 0 | 0 | 2 | 0 |
| BLS | 2 | 0 | 2 | 0 | 0 |
| BRAZE_USER_EVENT_DEMO_DATASET | 2 | 0 | 2 | 0 | 0 |
| COVID19_OPEN_DATA | 2 | 0 | 2 | 0 | 0 |
| COVID19_SYMPTOM_SEARCH | 2 | 0 | 2 | 0 | 0 |
| COVID19_USA | 2 | 0 | 2 | 0 | 0 |
| CYMBAL_INVESTMENTS | 2 | 0 | 2 | 0 | 0 |
| DEATH | 2 | 0 | 2 | 0 | 0 |
| EBI_CHEMBL | 2 | 0 | 2 | 0 | 0 |
| ECOMMERCE | 2 | 0 | 2 | 0 | 0 |
| FEC | 2 | 0 | 2 | 0 | 0 |
| FHIR_SYNTHEA | 2 | 0 | 2 | 0 | 0 |
| GENOMICS_CANNABIS | 2 | 0 | 2 | 0 | 0 |
| GHCN_D | 2 | 0 | 2 | 0 | 0 |
| GOOGLE_ADS | 2 | 0 | 2 | 0 | 0 |
| GOOGLE_TRENDS | 2 | 0 | 2 | 0 | 0 |
| HTAN_2 | 2 | 0 | 2 | 0 | 0 |
| HUMAN_GENOME_VARIANTS | 2 | 0 | 2 | 0 | 0 |
| IMDB_MOVIES | 2 | 0 | 2 | 0 | 0 |
| MITELMAN | 2 | 0 | 2 | 0 | 0 |
| NETHERLANDS_OPEN_MAP_DATA | 2 | 0 | 0 | 2 | 0 |
| NOAA_DATA_PLUS | 2 | 0 | 2 | 0 | 0 |
| NOAA_PORTS | 2 | 0 | 2 | 0 | 0 |
| NORTHWIND | 2 | 0 | 2 | 0 | 0 |
| PAGILA | 2 | 0 | 2 | 0 | 0 |
| PANCANCER_ATLAS_2 | 2 | 0 | 2 | 0 | 0 |
| PATENTS_USPTO | 2 | 0 | 2 | 0 | 0 |
| SAN_FRANCISCO | 2 | 0 | 2 | 0 | 0 |
| ADVENTUREWORKS | 1 | 0 | 1 | 0 | 0 |
| AMAZON_VENDOR_ANALYTICS__SAMPLE_DATASET | 1 | 0 | 0 | 1 | 0 |
| BOWLINGLEAGUE | 1 | 0 | 1 | 0 | 0 |
| CENSUS_BUREAU_USA | 1 | 0 | 1 | 0 | 0 |
| CENSUS_GALAXY__AIML_MODEL_DATA_ENRICHMENT_SAMPLE | 1 | 0 | 1 | 0 | 0 |
| CENSUS_GALAXY__ZIP_CODE_TO_BLOCK_GROUP_SAMPLE | 1 | 0 | 1 | 0 | 0 |
| COVID19_JHU_WORLD_BANK | 1 | 0 | 1 | 0 | 0 |
| COVID19_NYT | 1 | 0 | 1 | 0 | 0 |
| COVID19_OPEN_WORLD_BANK | 1 | 0 | 1 | 0 | 0 |
| CPTAC_PDC | 1 | 0 | 1 | 0 | 0 |
| DIMENSIONS_AI_COVID19 | 1 | 0 | 1 | 0 | 0 |
| ECLIPSE_MEGAMOVIE | 1 | 0 | 1 | 0 | 0 |
| ELECTRONIC_SALES | 1 | 0 | 1 | 0 | 0 |
| EPA_HISTORICAL_AIR_QUALITY | 1 | 0 | 1 | 0 | 0 |
| GBIF | 1 | 0 | 1 | 0 | 0 |
| GEO_OPENSTREETMAP_BOUNDARIES | 1 | 0 | 1 | 0 | 0 |
| GEO_OPENSTREETMAP_CENSUS_PLACES | 1 | 0 | 1 | 0 | 0 |
| GEO_OPENSTREETMAP_WORLDPOP | 1 | 0 | 1 | 0 | 0 |
| GLOBAL_GOVERNMENT | 1 | 0 | 1 | 0 | 0 |
| GLOBAL_WEATHER__CLIMATE_DATA_FOR_BI | 1 | 0 | 0 | 1 | 0 |
| HACKER_NEWS | 1 | 0 | 1 | 0 | 0 |
| HTAN_1 | 1 | 0 | 1 | 0 | 0 |
| IOWA_LIQUOR_SALES_PLUS | 1 | 0 | 1 | 0 | 0 |
| IRS_990 | 1 | 0 | 1 | 0 | 0 |
| LIBRARIES_IO | 1 | 0 | 1 | 0 | 0 |
| MLB | 1 | 0 | 1 | 0 | 0 |
| MUSIC | 1 | 0 | 1 | 0 | 0 |
| NCAA_INSIGHTS | 1 | 0 | 1 | 0 | 0 |
| NEW_YORK_GEO | 1 | 0 | 1 | 0 | 0 |
| NEW_YORK_GHCN | 1 | 0 | 1 | 0 | 0 |
| NHTSA_TRAFFIC_FATALITIES_PLUS | 1 | 0 | 1 | 0 | 0 |
| NOAA_GLOBAL_FORECAST_SYSTEM | 1 | 0 | 1 | 0 | 0 |
| NOAA_GSOD | 1 | 0 | 1 | 0 | 0 |
| NPPES | 1 | 0 | 1 | 0 | 0 |
| OPENAQ | 1 | 0 | 1 | 0 | 0 |
| OPEN_IMAGES | 1 | 0 | 1 | 0 | 0 |
| OPEN_TARGETS_GENETICS_1 | 1 | 0 | 1 | 0 | 0 |
| OPEN_TARGETS_GENETICS_2 | 1 | 0 | 1 | 0 | 0 |
| OPEN_TARGETS_PLATFORM_2 | 1 | 0 | 1 | 0 | 0 |
| PYPI | 1 | 0 | 1 | 0 | 0 |
| SCHOOL_SCHEDULING | 1 | 0 | 1 | 0 | 0 |
| SEC_QUARTERLY_FINANCIALS | 1 | 0 | 1 | 0 | 0 |
| STACKOVERFLOW_PLUS | 1 | 0 | 1 | 0 | 0 |
| SUNROOF_SOLAR | 1 | 0 | 1 | 0 | 0 |
| TARGETOME_REACTOME | 1 | 0 | 1 | 0 | 0 |
| TCGA_BIOCLIN_V0 | 1 | 0 | 1 | 0 | 0 |
| TCGA_HG19_DATA_V0 | 1 | 0 | 1 | 0 | 0 |
| USDA_NASS_AGRICULTURE | 1 | 0 | 1 | 0 | 0 |
| US_ADDRESSES__POI | 1 | 0 | 1 | 0 | 0 |
| WEATHER__ENVIRONMENT | 1 | 0 | 1 | 0 | 0 |
| WWE | 1 | 0 | 1 | 0 | 0 |
| YES_ENERGY__SAMPLE_DATA | 1 | 0 | 1 | 0 | 0 |

Top error signatures:
- 3x `003030 (02000): SQL compilation error:`
- 1x `002003 (02000): SQL compilation error:`
- 1x `000904 (42000): SQL compilation error: error line 3 at position 32`
- 1x `000904 (42000): SQL compilation error: error line 3 at position 8`
- 1x `000904 (42000): SQL compilation error: error line 50 at position 97`

Broken task IDs:
- `sf001` (GLOBAL_WEATHER__CLIMATE_DATA_FOR_BI): `002003 (02000): SQL compilation error:`
- `sf009` (NETHERLANDS_OPEN_MAP_DATA): `003030 (02000): SQL compilation error:`
- `sf013` (NETHERLANDS_OPEN_MAP_DATA): `003030 (02000): SQL compilation error:`
- `sf029` (AMAZON_VENDOR_ANALYTICS__SAMPLE_DATASET): `003030 (02000): SQL compilation error:`
- `sf_local007` (BASEBALL): `000904 (42000): SQL compilation error: error line 3 at position 32`
- `sf_local008` (BASEBALL): `000904 (42000): SQL compilation error: error line 3 at position 8`
- `sf_local032` (BRAZILIAN_E_COMMERCE): `000904 (42000): SQL compilation error: error line 50 at position 97`

Wrong-but-executed task IDs:
- `sf002` (FINANCE__ECONOMICS)
- `sf003` (GLOBAL_GOVERNMENT)
- `sf006` (FINANCE__ECONOMICS)
- `sf008` (US_REAL_ESTATE)
- `sf010` (US_REAL_ESTATE)
- `sf011` (CENSUS_GALAXY__ZIP_CODE_TO_BLOCK_GROUP_SAMPLE)
- `sf012` (WEATHER__ENVIRONMENT)
- `sf014` (CENSUS_GALAXY__AIML_MODEL_DATA_ENRICHMENT_SAMPLE)
- `sf018` (BRAZE_USER_EVENT_DEMO_DATASET)
- `sf035` (BRAZE_USER_EVENT_DEMO_DATASET)
- `sf037` (US_REAL_ESTATE)
- `sf040` (US_ADDRESSES__POI)
- `sf041` (YES_ENERGY__SAMPLE_DATA)
- `sf044` (FINANCE__ECONOMICS)
- `sf_bq001` (GA360)
- `sf_bq002` (GA360)
- `sf_bq003` (GA360)
- `sf_bq004` (GA360)
- `sf_bq005` (CRYPTO)
- `sf_bq007` (CENSUS_BUREAU_ACS_2)
- `sf_bq008` (GA360)
- `sf_bq009` (GA360)
- `sf_bq010` (GA360)
- `sf_bq011` (GA4)
- `sf_bq012` (ETHEREUM_BLOCKCHAIN)
- `sf_bq014` (THELOOK_ECOMMERCE)
- `sf_bq015` (STACKOVERFLOW_PLUS)
- `sf_bq016` (DEPS_DEV_V1)
- `sf_bq017` (GEO_OPENSTREETMAP)
- `sf_bq018` (COVID19_OPEN_DATA)
- `sf_bq019` (CMS_DATA)
- `sf_bq020` (GENOMICS_CANNABIS)
- `sf_bq021` (NEW_YORK)
- `sf_bq023` (FEC)
- `sf_bq024` (USFS_FIA)
- `sf_bq025` (CENSUS_BUREAU_INTERNATIONAL)
- `sf_bq026` (PATENTS)
- `sf_bq027` (PATENTS)
- `sf_bq028` (DEPS_DEV_V1)
- `sf_bq029` (PATENTS)
- `sf_bq030` (COVID19_OPEN_DATA)
- `sf_bq031` (NOAA_DATA)
- `sf_bq032` (NOAA_DATA)
- `sf_bq033` (PATENTS)
- `sf_bq034` (GHCN_D)
- `sf_bq035` (SAN_FRANCISCO)
- `sf_bq036` (GITHUB_REPOS)
- `sf_bq037` (HUMAN_GENOME_VARIANTS)
- `sf_bq038` (NEW_YORK)
- `sf_bq039` (NEW_YORK_PLUS)
- `sf_bq040` (NEW_YORK_PLUS)
- `sf_bq041` (STACKOVERFLOW)
- `sf_bq042` (NOAA_DATA)
- `sf_bq043` (TCGA)
- `sf_bq044` (TCGA)
- `sf_bq045` (NOAA_DATA)
- `sf_bq046` (TCGA_BIOCLIN_V0)
- `sf_bq047` (NEW_YORK_NOAA)
- `sf_bq048` (NEW_YORK_NOAA)
- `sf_bq049` (IOWA_LIQUOR_SALES_PLUS)
- `sf_bq050` (NEW_YORK_CITIBIKE_1)
- `sf_bq051` (NEW_YORK_GHCN)
- `sf_bq052` (PATENTSVIEW)
- `sf_bq053` (NEW_YORK)
- `sf_bq054` (NEW_YORK)
- `sf_bq055` (GOOGLE_DEI)
- `sf_bq056` (GEO_OPENSTREETMAP_BOUNDARIES)
- `sf_bq057` (CRYPTO)
- `sf_bq058` (GOOG_BLOCKCHAIN)
- `sf_bq059` (SAN_FRANCISCO_PLUS)
- `sf_bq060` (CENSUS_BUREAU_INTERNATIONAL)
- `sf_bq061` (CENSUS_BUREAU_ACS_1)
- `sf_bq062` (DEPS_DEV_V1)
- `sf_bq063` (DEPS_DEV_V1)
- `sf_bq064` (CENSUS_BUREAU_ACS_1)
- `sf_bq065` (CRYPTO)
- `sf_bq066` (SDOH)
- `sf_bq067` (NHTSA_TRAFFIC_FATALITIES)
- `sf_bq068` (CRYPTO)
- `sf_bq069` (IDC)
- `sf_bq070` (IDC)
- `sf_bq071` (NOAA_DATA_PLUS)
- `sf_bq072` (DEATH)
- `sf_bq073` (CENSUS_BUREAU_ACS_2)
- `sf_bq074` (SDOH)
- `sf_bq075` (GOOGLE_DEI)
- `sf_bq078` (OPEN_TARGETS_PLATFORM_2)
- `sf_bq079` (USFS_FIA)
- `sf_bq080` (CRYPTO)
- `sf_bq081` (SAN_FRANCISCO_PLUS)
- `sf_bq083` (CRYPTO)
- `sf_bq084` (GOOG_BLOCKCHAIN)
- `sf_bq085` (COVID19_JHU_WORLD_BANK)
- `sf_bq086` (COVID19_OPEN_WORLD_BANK)
- `sf_bq087` (COVID19_SYMPTOM_SEARCH)
- `sf_bq088` (COVID19_SYMPTOM_SEARCH)
- `sf_bq089` (COVID19_USA)
- `sf_bq090` (CYMBAL_INVESTMENTS)
- `sf_bq091` (PATENTS)
- `sf_bq092` (CRYPTO)
- `sf_bq093` (CRYPTO)
- `sf_bq094` (FEC)
- `sf_bq095` (OPEN_TARGETS_PLATFORM_1)
- `sf_bq096` (GBIF)
- `sf_bq097` (SDOH)
- `sf_bq098` (NEW_YORK_PLUS)
- `sf_bq099` (PATENTS)
- `sf_bq100` (GITHUB_REPOS)
- `sf_bq101` (GITHUB_REPOS)
- `sf_bq102` (GNOMAD)
- `sf_bq103` (GNOMAD)
- `sf_bq104` (GOOGLE_TRENDS)
- `sf_bq105` (NHTSA_TRAFFIC_FATALITIES_PLUS)
- `sf_bq107` (GENOMICS_CANNABIS)
- `sf_bq108` (NHTSA_TRAFFIC_FATALITIES)
- `sf_bq109` (OPEN_TARGETS_GENETICS_1)
- `sf_bq110` (SDOH)
- `sf_bq111` (TCGA_MITELMAN)
- `sf_bq112` (BLS)
- `sf_bq113` (BLS)
- `sf_bq114` (OPENAQ)
- `sf_bq115` (CENSUS_BUREAU_INTERNATIONAL)
- `sf_bq116` (SEC_QUARTERLY_FINANCIALS)
- `sf_bq117` (NOAA_DATA)
- `sf_bq118` (DEATH)
- `sf_bq119` (NOAA_DATA)
- `sf_bq120` (SDOH)
- `sf_bq121` (STACKOVERFLOW)
- `sf_bq123` (STACKOVERFLOW)
- `sf_bq124` (FHIR_SYNTHEA)
- `sf_bq126` (THE_MET)
- `sf_bq127` (PATENTS_GOOGLE)
- `sf_bq128` (PATENTSVIEW)
- `sf_bq130` (COVID19_NYT)
- `sf_bq131` (GEO_OPENSTREETMAP)
- `sf_bq135` (CRYPTO)
- `sf_bq136` (CRYPTO)
- `sf_bq137` (CENSUS_BUREAU_USA)
- `sf_bq141` (TCGA_HG38_DATA_V0)
- `sf_bq143` (CPTAC_PDC)
- `sf_bq144` (NCAA_INSIGHTS)
- `sf_bq147` (TCGA)
- `sf_bq148` (TCGA)
- `sf_bq150` (TCGA_HG19_DATA_V0)
- `sf_bq151` (PANCANCER_ATLAS_2)
- `sf_bq152` (TCGA_HG38_DATA_V0)
- `sf_bq153` (PANCANCER_ATLAS_1)
- `sf_bq154` (PANCANCER_ATLAS_1)
- `sf_bq155` (TCGA_HG38_DATA_V0)
- `sf_bq156` (PANCANCER_ATLAS_1)
- `sf_bq157` (PANCANCER_ATLAS_1)
- `sf_bq158` (PANCANCER_ATLAS_1)
- `sf_bq159` (PANCANCER_ATLAS_1)
- `sf_bq160` (META_KAGGLE)
- `sf_bq161` (PANCANCER_ATLAS_2)
- `sf_bq162` (HTAN_1)
- `sf_bq163` (HTAN_2)
- `sf_bq164` (HTAN_2)
- `sf_bq165` (MITELMAN)
- `sf_bq166` (TCGA_MITELMAN)
- `sf_bq167` (META_KAGGLE)
- `sf_bq169` (MITELMAN)
- `sf_bq171` (META_KAGGLE)
- `sf_bq172` (CMS_DATA)
- `sf_bq177` (CMS_DATA)
- `sf_bq180` (GITHUB_REPOS)
- `sf_bq181` (NOAA_DATA)
- `sf_bq182` (GITHUB_REPOS_DATE)
- `sf_bq184` (CRYPTO)
- `sf_bq185` (NEW_YORK_PLUS)
- `sf_bq186` (SAN_FRANCISCO)
- `sf_bq187` (ETHEREUM_BLOCKCHAIN)
- `sf_bq188` (THELOOK_ECOMMERCE)
- `sf_bq189` (THELOOK_ECOMMERCE)
- `sf_bq190` (THELOOK_ECOMMERCE)
- `sf_bq191` (GITHUB_REPOS_DATE)
- `sf_bq192` (GITHUB_REPOS_DATE)
- `sf_bq193` (GITHUB_REPOS)
- `sf_bq194` (GITHUB_REPOS)
- `sf_bq195` (CRYPTO)
- `sf_bq197` (THELOOK_ECOMMERCE)
- `sf_bq198` (NCAA_BASKETBALL)
- `sf_bq199` (IOWA_LIQUOR_SALES)
- `sf_bq200` (MLB)
- `sf_bq202` (NEW_YORK_PLUS)
- `sf_bq203` (NEW_YORK_PLUS)
- `sf_bq204` (ECLIPSE_MEGAMOVIE)
- `sf_bq207` (PATENTS_USPTO)
- `sf_bq208` (NEW_YORK_NOAA)
- `sf_bq209` (PATENTS)
- `sf_bq210` (PATENTS)
- `sf_bq211` (PATENTS)
- `sf_bq212` (PATENTS)
- `sf_bq213` (PATENTS)
- `sf_bq214` (PATENTS_GOOGLE)
- `sf_bq215` (PATENTS)
- `sf_bq216` (PATENTS_GOOGLE)
- `sf_bq217` (GITHUB_REPOS_DATE)
- `sf_bq218` (IOWA_LIQUOR_SALES)
- `sf_bq219` (IOWA_LIQUOR_SALES)
- `sf_bq220` (USFS_FIA)
- `sf_bq221` (PATENTS)
- `sf_bq222` (PATENTS)
- `sf_bq223` (PATENTS)
- `sf_bq224` (GITHUB_REPOS_DATE)
- `sf_bq225` (GITHUB_REPOS)
- `sf_bq226` (GOOG_BLOCKCHAIN)
- `sf_bq227` (LONDON)
- `sf_bq228` (LONDON)
- `sf_bq229` (OPEN_IMAGES)
- `sf_bq230` (USDA_NASS_AGRICULTURE)
- `sf_bq232` (LONDON)
- `sf_bq233` (GITHUB_REPOS)
- `sf_bq234` (CMS_DATA)
- `sf_bq235` (CMS_DATA)
- `sf_bq236` (NOAA_DATA_PLUS)
- `sf_bq246` (PATENTSVIEW)
- `sf_bq247` (PATENTS_GOOGLE)
- `sf_bq248` (GITHUB_REPOS)
- `sf_bq249` (GITHUB_REPOS)
- `sf_bq250` (GEO_OPENSTREETMAP_WORLDPOP)
- `sf_bq251` (PYPI)
- `sf_bq252` (GITHUB_REPOS)
- `sf_bq253` (GEO_OPENSTREETMAP)
- `sf_bq254` (GEO_OPENSTREETMAP)
- `sf_bq255` (GITHUB_REPOS)
- `sf_bq256` (CRYPTO)
- `sf_bq258` (THELOOK_ECOMMERCE)
- `sf_bq259` (THELOOK_ECOMMERCE)
- `sf_bq260` (THELOOK_ECOMMERCE)
- `sf_bq261` (THELOOK_ECOMMERCE)
- `sf_bq262` (THELOOK_ECOMMERCE)
- `sf_bq263` (THELOOK_ECOMMERCE)
- `sf_bq264` (THELOOK_ECOMMERCE)
- `sf_bq265` (THELOOK_ECOMMERCE)
- `sf_bq266` (THELOOK_ECOMMERCE)
- `sf_bq268` (GA360)
- `sf_bq269` (GA360)
- `sf_bq270` (GA360)
- `sf_bq271` (THELOOK_ECOMMERCE)
- `sf_bq272` (THELOOK_ECOMMERCE)
- `sf_bq273` (THELOOK_ECOMMERCE)
- `sf_bq275` (GA360)
- `sf_bq276` (NOAA_PORTS)
- `sf_bq277` (NOAA_PORTS)
- `sf_bq278` (SUNROOF_SOLAR)
- `sf_bq280` (STACKOVERFLOW)
- `sf_bq283` (AUSTIN)
- `sf_bq285` (FDA)
- `sf_bq287` (FDA)
- `sf_bq288` (FDA)
- `sf_bq289` (GEO_OPENSTREETMAP_CENSUS_PLACES)
- `sf_bq290` (NOAA_DATA)
- `sf_bq291` (NOAA_GLOBAL_FORECAST_SYSTEM)
- `sf_bq292` (CRYPTO)
- `sf_bq293` (NEW_YORK_GEO)
- `sf_bq294` (SAN_FRANCISCO_PLUS)
- `sf_bq295` (GITHUB_REPOS_DATE)
- `sf_bq300` (STACKOVERFLOW)
- `sf_bq301` (STACKOVERFLOW)
- `sf_bq302` (STACKOVERFLOW)
- `sf_bq303` (STACKOVERFLOW)
- `sf_bq304` (STACKOVERFLOW)
- `sf_bq305` (STACKOVERFLOW)
- `sf_bq306` (STACKOVERFLOW)
- `sf_bq307` (STACKOVERFLOW)
- `sf_bq308` (STACKOVERFLOW)
- `sf_bq309` (STACKOVERFLOW)
- `sf_bq310` (STACKOVERFLOW)
- `sf_bq320` (IDC)
- `sf_bq321` (IDC)
- `sf_bq323` (IDC)
- `sf_bq324` (IDC)
- `sf_bq325` (OPEN_TARGETS_GENETICS_2)
- `sf_bq326` (WORLD_BANK)
- `sf_bq327` (WORLD_BANK)
- `sf_bq328` (WORLD_BANK)
- `sf_bq330` (FDA)
- `sf_bq331` (META_KAGGLE)
- `sf_bq333` (THELOOK_ECOMMERCE)
- `sf_bq334` (CRYPTO)
- `sf_bq335` (CRYPTO)
- `sf_bq338` (CENSUS_BUREAU_ACS_1)
- `sf_bq339` (SAN_FRANCISCO_PLUS)
- `sf_bq340` (CRYPTO)
- `sf_bq341` (CRYPTO)
- `sf_bq342` (CRYPTO)
- `sf_bq345` (IDC)
- `sf_bq346` (IDC)
- `sf_bq347` (IDC)
- `sf_bq348` (GEO_OPENSTREETMAP)
- `sf_bq349` (GEO_OPENSTREETMAP)
- `sf_bq350` (OPEN_TARGETS_PLATFORM_1)
- `sf_bq352` (SDOH)
- `sf_bq354` (CMS_DATA)
- `sf_bq355` (CMS_DATA)
- `sf_bq356` (NOAA_DATA)
- `sf_bq357` (NOAA_DATA)
- `sf_bq358` (NEW_YORK_CITIBIKE_1)
- `sf_bq359` (GITHUB_REPOS)
- `sf_bq360` (NPPES)
- `sf_bq361` (THELOOK_ECOMMERCE)
- `sf_bq366` (THE_MET)
- `sf_bq370` (WIDE_WORLD_IMPORTERS)
- `sf_bq371` (WIDE_WORLD_IMPORTERS)
- `sf_bq372` (WIDE_WORLD_IMPORTERS)
- `sf_bq373` (WIDE_WORLD_IMPORTERS)
- `sf_bq374` (GA360)
- `sf_bq375` (GITHUB_REPOS)
- `sf_bq376` (SAN_FRANCISCO_PLUS)
- `sf_bq377` (GITHUB_REPOS)
- `sf_bq379` (OPEN_TARGETS_PLATFORM_1)
- `sf_bq380` (META_KAGGLE)
- `sf_bq383` (GHCN_D)
- `sf_bq389` (EPA_HISTORICAL_AIR_QUALITY)
- `sf_bq390` (IDC)
- `sf_bq391` (FHIR_SYNTHEA)
- `sf_bq392` (NOAA_GSOD)
- `sf_bq393` (HACKER_NEWS)
- `sf_bq394` (NOAA_DATA)
- `sf_bq395` (SDOH)
- `sf_bq396` (NHTSA_TRAFFIC_FATALITIES)
- `sf_bq397` (ECOMMERCE)
- `sf_bq398` (WORLD_BANK)
- `sf_bq399` (WORLD_BANK)
- `sf_bq400` (SAN_FRANCISCO_PLUS)
- `sf_bq402` (ECOMMERCE)
- `sf_bq403` (IRS_990)
- `sf_bq406` (GOOGLE_DEI)
- `sf_bq407` (COVID19_USA)
- `sf_bq410` (CENSUS_BUREAU_ACS_2)
- `sf_bq411` (GOOGLE_TRENDS)
- `sf_bq412` (GOOGLE_ADS)
- `sf_bq413` (DIMENSIONS_AI_COVID19)
- `sf_bq414` (THE_MET)
- `sf_bq415` (HUMAN_GENOME_VARIANTS)
- `sf_bq416` (GOOG_BLOCKCHAIN)
- `sf_bq417` (IDC)
- `sf_bq418` (TARGETOME_REACTOME)
- `sf_bq419` (NOAA_DATA)
- `sf_bq420` (PATENTS_USPTO)
- `sf_bq421` (IDC)
- `sf_bq422` (IDC)
- `sf_bq423` (GOOGLE_ADS)
- `sf_bq424` (WORLD_BANK)
- `sf_bq425` (EBI_CHEMBL)
- `sf_bq426` (NEW_YORK_CITIBIKE_1)
- `sf_bq427` (NCAA_BASKETBALL)
- `sf_bq428` (NCAA_BASKETBALL)
- `sf_bq429` (CENSUS_BUREAU_ACS_2)
- `sf_bq430` (EBI_CHEMBL)
- `sf_bq432` (FDA)
- `sf_bq441` (NHTSA_TRAFFIC_FATALITIES)
- `sf_bq442` (CYMBAL_INVESTMENTS)
- `sf_bq444` (CRYPTO)
- `sf_bq445` (GNOMAD)
- `sf_bq450` (ETHEREUM_BLOCKCHAIN)
- `sf_bq451` (_1000_GENOMES)
- `sf_bq452` (_1000_GENOMES)
- `sf_bq453` (_1000_GENOMES)
- `sf_bq454` (_1000_GENOMES)
- `sf_bq455` (IDC)
- `sf_bq456` (IDC)
- `sf_bq457` (LIBRARIES_IO)
- `sf_bq458` (WORD_VECTORS_US)
- `sf_bq459` (WORD_VECTORS_US)
- `sf_bq460` (WORD_VECTORS_US)
- `sf_bq461` (NCAA_BASKETBALL)
- `sf_bq462` (NCAA_BASKETBALL)
- `sf_ga001` (GA4)
- `sf_ga002` (GA4)
- `sf_ga003` (FIREBASE)
- `sf_ga004` (GA4)
- `sf_ga005` (FIREBASE)
- `sf_ga006` (GA4)
- `sf_ga007` (GA4)
- `sf_ga008` (GA4)
- `sf_ga009` (GA4)
- `sf_ga010` (GA4)
- `sf_ga011` (GA4)
- `sf_ga012` (GA4)
- `sf_ga013` (GA4)
- `sf_ga014` (GA4)
- `sf_ga017` (GA4)
- `sf_ga018` (GA4)
- `sf_ga019` (FIREBASE)
- `sf_ga020` (FIREBASE)
- `sf_ga021` (FIREBASE)
- `sf_ga022` (FIREBASE)
- `sf_ga025` (FIREBASE)
- `sf_ga028` (FIREBASE)
- `sf_ga030` (FIREBASE)
- `sf_ga031` (GA4)
- `sf_ga032` (GA4)
- `sf_local002` (E_COMMERCE)
- `sf_local003` (E_COMMERCE)
- `sf_local004` (E_COMMERCE)
- `sf_local009` (AIRLINES)
- `sf_local010` (AIRLINES)
- `sf_local015` (CALIFORNIA_TRAFFIC_COLLISION)
- `sf_local017` (CALIFORNIA_TRAFFIC_COLLISION)
- `sf_local018` (CALIFORNIA_TRAFFIC_COLLISION)
- `sf_local019` (WWE)
- `sf_local020` (IPL)
- `sf_local021` (IPL)
- `sf_local022` (IPL)
- `sf_local023` (IPL)
- `sf_local024` (IPL)
- `sf_local025` (IPL)
- `sf_local026` (IPL)
- `sf_local029` (BRAZILIAN_E_COMMERCE)
- `sf_local034` (BRAZILIAN_E_COMMERCE)
- `sf_local038` (PAGILA)
- `sf_local039` (PAGILA)
- `sf_local040` (MODERN_DATA)
- `sf_local041` (MODERN_DATA)
- `sf_local049` (MODERN_DATA)
- `sf_local050` (COMPLEX_ORACLE)
- `sf_local054` (CHINOOK)
- `sf_local055` (CHINOOK)
- `sf_local056` (SQLITE_SAKILA)
- `sf_local058` (EDUCATION_BUSINESS)
- `sf_local059` (EDUCATION_BUSINESS)
- `sf_local060` (COMPLEX_ORACLE)
- `sf_local061` (COMPLEX_ORACLE)
- `sf_local062` (COMPLEX_ORACLE)
- `sf_local063` (COMPLEX_ORACLE)
- `sf_local064` (BANK_SALES_TRADING)
- `sf_local065` (MODERN_DATA)
- `sf_local066` (MODERN_DATA)
- `sf_local067` (COMPLEX_ORACLE)
- `sf_local068` (CITY_LEGISLATION)
- `sf_local070` (CITY_LEGISLATION)
- `sf_local071` (CITY_LEGISLATION)
- `sf_local072` (CITY_LEGISLATION)
- `sf_local073` (MODERN_DATA)
- `sf_local074` (BANK_SALES_TRADING)
- `sf_local075` (BANK_SALES_TRADING)
- `sf_local077` (BANK_SALES_TRADING)
- `sf_local078` (BANK_SALES_TRADING)
- `sf_local081` (NORTHWIND)
- `sf_local085` (NORTHWIND)
- `sf_local096` (DB_IMDB)
- `sf_local097` (DB_IMDB)
- `sf_local098` (DB_IMDB)
- `sf_local099` (DB_IMDB)
- `sf_local100` (DB_IMDB)
- `sf_local114` (EDUCATION_BUSINESS)
- `sf_local128` (BOWLINGLEAGUE)
- `sf_local130` (SCHOOL_SCHEDULING)
- `sf_local131` (ENTERTAINMENTAGENCY)
- `sf_local132` (ENTERTAINMENTAGENCY)
- `sf_local133` (ENTERTAINMENTAGENCY)
- `sf_local141` (ADVENTUREWORKS)
- `sf_local152` (IMDB_MOVIES)
- `sf_local156` (BANK_SALES_TRADING)
- `sf_local157` (BANK_SALES_TRADING)
- `sf_local163` (EDUCATION_BUSINESS)
- `sf_local167` (CITY_LEGISLATION)
- `sf_local168` (CITY_LEGISLATION)
- `sf_local169` (CITY_LEGISLATION)
- `sf_local170` (CITY_LEGISLATION)
- `sf_local171` (CITY_LEGISLATION)
- `sf_local193` (SQLITE_SAKILA)
- `sf_local194` (SQLITE_SAKILA)
- `sf_local195` (SQLITE_SAKILA)
- `sf_local196` (SQLITE_SAKILA)
- `sf_local197` (SQLITE_SAKILA)
- `sf_local198` (CHINOOK)
- `sf_local199` (SQLITE_SAKILA)
- `sf_local201` (MODERN_DATA)
- `sf_local202` (CITY_LEGISLATION)
- `sf_local209` (DELIVERY_CENTER)
- `sf_local210` (DELIVERY_CENTER)
- `sf_local212` (DELIVERY_CENTER)
- `sf_local218` (EU_SOCCER)
- `sf_local219` (EU_SOCCER)
- `sf_local220` (EU_SOCCER)
- `sf_local221` (EU_SOCCER)
- `sf_local228` (IPL)
- `sf_local229` (IPL)
- `sf_local230` (IMDB_MOVIES)
- `sf_local244` (MUSIC)
- `sf_local253` (EDUCATION_BUSINESS)
- `sf_local258` (IPL)
- `sf_local259` (IPL)
- `sf_local262` (STACKING)
- `sf_local263` (STACKING)
- `sf_local264` (STACKING)
- `sf_local269` (ORACLE_SQL)
- `sf_local270` (ORACLE_SQL)
- `sf_local272` (ORACLE_SQL)
- `sf_local273` (ORACLE_SQL)
- `sf_local274` (ORACLE_SQL)
- `sf_local275` (ORACLE_SQL)
- `sf_local277` (ORACLE_SQL)
- `sf_local279` (ORACLE_SQL)
- `sf_local283` (EU_SOCCER)
- `sf_local284` (BANK_SALES_TRADING)
- `sf_local285` (BANK_SALES_TRADING)
- `sf_local286` (ELECTRONIC_SALES)
- `sf_local297` (BANK_SALES_TRADING)
- `sf_local298` (BANK_SALES_TRADING)
- `sf_local299` (BANK_SALES_TRADING)
- `sf_local300` (BANK_SALES_TRADING)
- `sf_local301` (BANK_SALES_TRADING)
- `sf_local302` (BANK_SALES_TRADING)
- `sf_local309` (F1)
- `sf_local310` (F1)
- `sf_local311` (F1)
- `sf_local329` (LOG)
- `sf_local330` (LOG)
- `sf_local331` (LOG)
- `sf_local335` (F1)
- `sf_local336` (F1)
- `sf_local344` (F1)
- `sf_local354` (F1)
- `sf_local355` (F1)
- `sf_local356` (F1)
- `sf_local358` (LOG)
- `sf_local360` (LOG)

## Overall

- Total tasks: 1094
- Solved: 31
- Wrong: 521
- Broken: 542
- Indeterminate: 0

Top error signatures across both benchmarks:
- 20x `'No schema snapshot registered for db_id=CRYPTO'`
- 19x `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- 17x `'No schema snapshot registered for db_id=ga4'`
- 15x `'No schema snapshot registered for db_id=bank_sales_trading'`
- 15x `'No schema snapshot registered for db_id=PATENTS'`
- 15x `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- 15x `'No schema snapshot registered for db_id=IDC'`
- 13x `'No schema snapshot registered for db_id=stackoverflow'`
- 12x `'No schema snapshot registered for db_id=ga360'`
- 11x `'No schema snapshot registered for db_id=noaa_data'`
- 11x `'No schema snapshot registered for db_id=IPL'`
- 10x `'No schema snapshot registered for db_id=city_legislation'`
- 9x `'No schema snapshot registered for db_id=firebase'`
- 9x `'No schema snapshot registered for db_id=f1'`
- 8x `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`
- 8x `'No schema snapshot registered for db_id=oracle_sql'`
- 7x `'No schema snapshot registered for db_id=cms_data'`
- 7x `'No schema snapshot registered for db_id=sdoh'`
- 7x `'No schema snapshot registered for db_id=modern_data'`
- 6x `'No schema snapshot registered for db_id=new_york_plus'`

All broken task IDs:
- `spider-lite-sql` / `bq001` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `spider-lite-sql` / `bq002` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `spider-lite-sql` / `bq003` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `spider-lite-sql` / `bq004` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `spider-lite-sql` / `bq006` (AUSTIN): `'No schema snapshot registered for db_id=austin'`
- `spider-lite-sql` / `bq008` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `spider-lite-sql` / `bq009` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `spider-lite-sql` / `bq010` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `spider-lite-sql` / `bq011` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `spider-lite-sql` / `bq018` (COVID19_OPEN_DATA): `'No schema snapshot registered for db_id=covid19_open_data'`
- `spider-lite-sql` / `bq019` (CMS_DATA): `'No schema snapshot registered for db_id=cms_data'`
- `spider-lite-sql` / `bq021` (NEW_YORK): `'No schema snapshot registered for db_id=new_york'`
- `spider-lite-sql` / `bq022` (CHICAGO): `'No schema snapshot registered for db_id=chicago'`
- `spider-lite-sql` / `bq023` (FEC): `'No schema snapshot registered for db_id=fec'`
- `spider-lite-sql` / `bq024` (USFS_FIA): `'No schema snapshot registered for db_id=usfs_fia'`
- `spider-lite-sql` / `bq025` (CENSUS_BUREAU_INTERNATIONAL): `'No schema snapshot registered for db_id=census_bureau_international'`
- `spider-lite-sql` / `bq030` (COVID19_OPEN_DATA): `'No schema snapshot registered for db_id=covid19_open_data'`
- `spider-lite-sql` / `bq031` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `spider-lite-sql` / `bq032` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `spider-lite-sql` / `bq034` (GHCN_D): `'No schema snapshot registered for db_id=ghcn_d'`
- `spider-lite-sql` / `bq035` (SAN_FRANCISCO): `'No schema snapshot registered for db_id=san_francisco'`
- `spider-lite-sql` / `bq038` (NEW_YORK): `'No schema snapshot registered for db_id=new_york'`
- `spider-lite-sql` / `bq039` (NEW_YORK_PLUS): `'No schema snapshot registered for db_id=new_york_plus'`
- `spider-lite-sql` / `bq040` (NEW_YORK_PLUS): `'No schema snapshot registered for db_id=new_york_plus'`
- `spider-lite-sql` / `bq041` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `spider-lite-sql` / `bq042` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `spider-lite-sql` / `bq045` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `spider-lite-sql` / `bq046` (TCGA_BIOCLIN_V0): `'No schema snapshot registered for db_id=TCGA_bioclin_v0'`
- `spider-lite-sql` / `bq047` (NEW_YORK_NOAA): `'No schema snapshot registered for db_id=new_york_noaa'`
- `spider-lite-sql` / `bq048` (NEW_YORK_NOAA): `'No schema snapshot registered for db_id=new_york_noaa'`
- `spider-lite-sql` / `bq049` (IOWA_LIQUOR_SALES_PLUS): `'No schema snapshot registered for db_id=iowa_liquor_sales_plus'`
- `spider-lite-sql` / `bq051` (NEW_YORK_GHCN): `'No schema snapshot registered for db_id=new_york_ghcn'`
- `spider-lite-sql` / `bq053` (NEW_YORK): `'No schema snapshot registered for db_id=new_york'`
- `spider-lite-sql` / `bq054` (NEW_YORK): `'No schema snapshot registered for db_id=new_york'`
- `spider-lite-sql` / `bq055` (GOOGLE_DEI): `'No schema snapshot registered for db_id=google_dei'`
- `spider-lite-sql` / `bq059` (SAN_FRANCISCO_PLUS): `'No schema snapshot registered for db_id=san_francisco_plus'`
- `spider-lite-sql` / `bq060` (CENSUS_BUREAU_INTERNATIONAL): `'No schema snapshot registered for db_id=census_bureau_international'`
- `spider-lite-sql` / `bq061` (CENSUS_BUREAU_ACS_1): `'No schema snapshot registered for db_id=census_bureau_acs_1'`
- `spider-lite-sql` / `bq064` (CENSUS_BUREAU_ACS_1): `'No schema snapshot registered for db_id=census_bureau_acs_1'`
- `spider-lite-sql` / `bq066` (SDOH): `'No schema snapshot registered for db_id=sdoh'`
- `spider-lite-sql` / `bq067` (NHTSA_TRAFFIC_FATALITIES): `'No schema snapshot registered for db_id=nhtsa_traffic_fatalities'`
- `spider-lite-sql` / `bq074` (SDOH): `'No schema snapshot registered for db_id=sdoh'`
- `spider-lite-sql` / `bq075` (GOOGLE_DEI): `'No schema snapshot registered for db_id=google_dei'`
- `spider-lite-sql` / `bq076` (CHICAGO): `'No schema snapshot registered for db_id=chicago'`
- `spider-lite-sql` / `bq077` (CHICAGO): `'No schema snapshot registered for db_id=chicago'`
- `spider-lite-sql` / `bq079` (USFS_FIA): `'No schema snapshot registered for db_id=usfs_fia'`
- `spider-lite-sql` / `bq081` (SAN_FRANCISCO_PLUS): `'No schema snapshot registered for db_id=san_francisco_plus'`
- `spider-lite-sql` / `bq085` (COVID19_JHU_WORLD_BANK): `'No schema snapshot registered for db_id=covid19_jhu_world_bank'`
- `spider-lite-sql` / `bq086` (COVID19_OPEN_WORLD_BANK): `'No schema snapshot registered for db_id=covid19_open_world_bank'`
- `spider-lite-sql` / `bq087` (COVID19_SYMPTOM_SEARCH): `'No schema snapshot registered for db_id=covid19_symptom_search'`
- `spider-lite-sql` / `bq088` (COVID19_SYMPTOM_SEARCH): `'No schema snapshot registered for db_id=covid19_symptom_search'`
- `spider-lite-sql` / `bq089` (COVID19_USA): `'No schema snapshot registered for db_id=covid19_usa'`
- `spider-lite-sql` / `bq090` (CYMBAL_INVESTMENTS): `'No schema snapshot registered for db_id=CYMBAL_INVESTMENTS'`
- `spider-lite-sql` / `bq094` (FEC): `'No schema snapshot registered for db_id=fec'`
- `spider-lite-sql` / `bq096` (GBIF): `'No schema snapshot registered for db_id=gbif'`
- `spider-lite-sql` / `bq097` (SDOH): `'No schema snapshot registered for db_id=sdoh'`
- `spider-lite-sql` / `bq098` (NEW_YORK_PLUS): `'No schema snapshot registered for db_id=new_york_plus'`
- `spider-lite-sql` / `bq102` (GNOMAD): `'No schema snapshot registered for db_id=gnomAD'`
- `spider-lite-sql` / `bq103` (GNOMAD): `'No schema snapshot registered for db_id=gnomAD'`
- `spider-lite-sql` / `bq105` (NHTSA_TRAFFIC_FATALITIES_PLUS): `'No schema snapshot registered for db_id=nhtsa_traffic_fatalities_plus'`
- `spider-lite-sql` / `bq108` (NHTSA_TRAFFIC_FATALITIES): `'No schema snapshot registered for db_id=nhtsa_traffic_fatalities'`
- `spider-lite-sql` / `bq109` (OPEN_TARGETS_GENETICS_1): `'No schema snapshot registered for db_id=open_targets_genetics_1'`
- `spider-lite-sql` / `bq110` (SDOH): `'No schema snapshot registered for db_id=sdoh'`
- `spider-lite-sql` / `bq111` (MITELMAN): `'No schema snapshot registered for db_id=mitelman'`
- `spider-lite-sql` / `bq112` (BLS): `'No schema snapshot registered for db_id=bls'`
- `spider-lite-sql` / `bq113` (BLS): `'No schema snapshot registered for db_id=bls'`
- `spider-lite-sql` / `bq114` (OPENAQ): `'No schema snapshot registered for db_id=openaq'`
- `spider-lite-sql` / `bq115` (CENSUS_BUREAU_INTERNATIONAL): `'No schema snapshot registered for db_id=census_bureau_international'`
- `spider-lite-sql` / `bq116` (SEC_QUARTERLY_FINANCIALS): `'No schema snapshot registered for db_id=sec_quarterly_financials'`
- `spider-lite-sql` / `bq119` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `spider-lite-sql` / `bq120` (SDOH): `'No schema snapshot registered for db_id=sdoh'`
- `spider-lite-sql` / `bq123` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `spider-lite-sql` / `bq124` (FHIR_SYNTHEA): `'No schema snapshot registered for db_id=fhir_synthea'`
- `spider-lite-sql` / `bq126` (THE_MET): `'No schema snapshot registered for db_id=the_met'`
- `spider-lite-sql` / `bq130` (COVID19_NYT): `'No schema snapshot registered for db_id=covid19_nyt'`
- `spider-lite-sql` / `bq137` (CENSUS_BUREAU_USA): `'No schema snapshot registered for db_id=census_bureau_usa'`
- `spider-lite-sql` / `bq143` (CPTAC_PDC): `'No schema snapshot registered for db_id=CPTAC_PDC'`
- `spider-lite-sql` / `bq144` (NCAA_INSIGHTS): `'No schema snapshot registered for db_id=ncaa_insights'`
- `spider-lite-sql` / `bq151` (PANCANCER_ATLAS_2): `'No schema snapshot registered for db_id=pancancer_atlas_2'`
- `spider-lite-sql` / `bq161` (PANCANCER_ATLAS_2): `'No schema snapshot registered for db_id=pancancer_atlas_2'`
- `spider-lite-sql` / `bq162` (HTAN_1): `'No schema snapshot registered for db_id=HTAN_1'`
- `spider-lite-sql` / `bq165` (MITELMAN): `'No schema snapshot registered for db_id=mitelman'`
- `spider-lite-sql` / `bq169` (MITELMAN): `'No schema snapshot registered for db_id=mitelman'`
- `spider-lite-sql` / `bq172` (CMS_DATA): `'No schema snapshot registered for db_id=cms_data'`
- `spider-lite-sql` / `bq177` (CMS_DATA): `'No schema snapshot registered for db_id=cms_data'`
- `spider-lite-sql` / `bq181` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `spider-lite-sql` / `bq185` (NEW_YORK_PLUS): `'No schema snapshot registered for db_id=new_york_plus'`
- `spider-lite-sql` / `bq186` (SAN_FRANCISCO): `'No schema snapshot registered for db_id=san_francisco'`
- `spider-lite-sql` / `bq198` (NCAA_BASKETBALL): `'No schema snapshot registered for db_id=ncaa_basketball'`
- `spider-lite-sql` / `bq199` (IOWA_LIQUOR_SALES): `'No schema snapshot registered for db_id=iowa_liquor_sales'`
- `spider-lite-sql` / `bq200` (MLB): `'No schema snapshot registered for db_id=mlb'`
- `spider-lite-sql` / `bq202` (NEW_YORK_PLUS): `'No schema snapshot registered for db_id=new_york_plus'`
- `spider-lite-sql` / `bq203` (NEW_YORK_PLUS): `'No schema snapshot registered for db_id=new_york_plus'`
- `spider-lite-sql` / `bq204` (ECLIPSE_MEGAMOVIE): `'No schema snapshot registered for db_id=eclipse_megamovie'`
- `spider-lite-sql` / `bq208` (NEW_YORK_NOAA): `'No schema snapshot registered for db_id=new_york_noaa'`
- `spider-lite-sql` / `bq218` (IOWA_LIQUOR_SALES): `'No schema snapshot registered for db_id=iowa_liquor_sales'`
- `spider-lite-sql` / `bq220` (USFS_FIA): `'No schema snapshot registered for db_id=usfs_fia'`
- `spider-lite-sql` / `bq227` (LONDON): `'No schema snapshot registered for db_id=london'`
- `spider-lite-sql` / `bq228` (LONDON): `'No schema snapshot registered for db_id=london'`
- `spider-lite-sql` / `bq229` (OPEN_IMAGES): `'No schema snapshot registered for db_id=open_images'`
- `spider-lite-sql` / `bq230` (USDA_NASS_AGRICULTURE): `'No schema snapshot registered for db_id=usda_nass_agriculture'`
- `spider-lite-sql` / `bq232` (LONDON): `'No schema snapshot registered for db_id=london'`
- `spider-lite-sql` / `bq234` (CMS_DATA): `'No schema snapshot registered for db_id=cms_data'`
- `spider-lite-sql` / `bq235` (CMS_DATA): `'No schema snapshot registered for db_id=cms_data'`
- `spider-lite-sql` / `bq268` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `spider-lite-sql` / `bq269` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `spider-lite-sql` / `bq270` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `spider-lite-sql` / `bq275` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `spider-lite-sql` / `bq277` (NOAA_PORTS): `'No schema snapshot registered for db_id=noaa_ports'`
- `spider-lite-sql` / `bq278` (SUNROOF_SOLAR): `'No schema snapshot registered for db_id=sunroof_solar'`
- `spider-lite-sql` / `bq279` (AUSTIN): `'No schema snapshot registered for db_id=austin'`
- `spider-lite-sql` / `bq280` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `spider-lite-sql` / `bq281` (AUSTIN): `'No schema snapshot registered for db_id=austin'`
- `spider-lite-sql` / `bq282` (AUSTIN): `'No schema snapshot registered for db_id=austin'`
- `spider-lite-sql` / `bq284` (BBC): `'No schema snapshot registered for db_id=bbc'`
- `spider-lite-sql` / `bq285` (FDA): `'No schema snapshot registered for db_id=fda'`
- `spider-lite-sql` / `bq286` (USA_NAMES): `'No schema snapshot registered for db_id=usa_names'`
- `spider-lite-sql` / `bq287` (FDA): `'No schema snapshot registered for db_id=fda'`
- `spider-lite-sql` / `bq288` (FDA): `'No schema snapshot registered for db_id=fda'`
- `spider-lite-sql` / `bq290` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `spider-lite-sql` / `bq293` (NEW_YORK_GEO): `'No schema snapshot registered for db_id=new_york_geo'`
- `spider-lite-sql` / `bq300` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `spider-lite-sql` / `bq301` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `spider-lite-sql` / `bq302` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `spider-lite-sql` / `bq303` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `spider-lite-sql` / `bq304` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `spider-lite-sql` / `bq305` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `spider-lite-sql` / `bq306` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `spider-lite-sql` / `bq308` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `spider-lite-sql` / `bq309` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `spider-lite-sql` / `bq310` (STACKOVERFLOW): `'No schema snapshot registered for db_id=stackoverflow'`
- `spider-lite-sql` / `bq326` (WORLD_BANK): `'No schema snapshot registered for db_id=world_bank'`
- `spider-lite-sql` / `bq327` (WORLD_BANK): `'No schema snapshot registered for db_id=world_bank'`
- `spider-lite-sql` / `bq328` (WORLD_BANK): `'No schema snapshot registered for db_id=world_bank'`
- `spider-lite-sql` / `bq330` (FDA): `'No schema snapshot registered for db_id=fda'`
- `spider-lite-sql` / `bq338` (CENSUS_BUREAU_ACS_1): `'No schema snapshot registered for db_id=census_bureau_acs_1'`
- `spider-lite-sql` / `bq339` (SAN_FRANCISCO_PLUS): `'No schema snapshot registered for db_id=san_francisco_plus'`
- `spider-lite-sql` / `bq352` (SDOH): `'No schema snapshot registered for db_id=sdoh'`
- `spider-lite-sql` / `bq354` (CMS_DATA): `'No schema snapshot registered for db_id=cms_data'`
- `spider-lite-sql` / `bq355` (CMS_DATA): `'No schema snapshot registered for db_id=cms_data'`
- `spider-lite-sql` / `bq356` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `spider-lite-sql` / `bq357` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `spider-lite-sql` / `bq360` (NPPES): `'No schema snapshot registered for db_id=nppes'`
- `spider-lite-sql` / `bq362` (CHICAGO): `'No schema snapshot registered for db_id=chicago'`
- `spider-lite-sql` / `bq363` (CHICAGO): `'No schema snapshot registered for db_id=chicago'`
- `spider-lite-sql` / `bq366` (THE_MET): `'No schema snapshot registered for db_id=the_met'`
- `spider-lite-sql` / `bq374` (GA360): `'No schema snapshot registered for db_id=ga360'`
- `spider-lite-sql` / `bq376` (SAN_FRANCISCO_PLUS): `'No schema snapshot registered for db_id=san_francisco_plus'`
- `spider-lite-sql` / `bq383` (GHCN_D): `'No schema snapshot registered for db_id=ghcn_d'`
- `spider-lite-sql` / `bq389` (EPA_HISTORICAL_AIR_QUALITY): `'No schema snapshot registered for db_id=epa_historical_air_quality'`
- `spider-lite-sql` / `bq391` (FHIR_SYNTHEA): `'No schema snapshot registered for db_id=fhir_synthea'`
- `spider-lite-sql` / `bq392` (NOAA_GSOD): `'No schema snapshot registered for db_id=noaa_gsod'`
- `spider-lite-sql` / `bq393` (HACKER_NEWS): `'No schema snapshot registered for db_id=hacker_news'`
- `spider-lite-sql` / `bq394` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `spider-lite-sql` / `bq395` (SDOH): `'No schema snapshot registered for db_id=sdoh'`
- `spider-lite-sql` / `bq396` (NHTSA_TRAFFIC_FATALITIES): `'No schema snapshot registered for db_id=nhtsa_traffic_fatalities'`
- `spider-lite-sql` / `bq397` (ECOMMERCE): `'No schema snapshot registered for db_id=ecommerce'`
- `spider-lite-sql` / `bq398` (WORLD_BANK): `'No schema snapshot registered for db_id=world_bank'`
- `spider-lite-sql` / `bq399` (WORLD_BANK): `'No schema snapshot registered for db_id=world_bank'`
- `spider-lite-sql` / `bq400` (SAN_FRANCISCO_PLUS): `'No schema snapshot registered for db_id=san_francisco_plus'`
- `spider-lite-sql` / `bq402` (ECOMMERCE): `'No schema snapshot registered for db_id=ecommerce'`
- `spider-lite-sql` / `bq403` (IRS_990): `'No schema snapshot registered for db_id=irs_990'`
- `spider-lite-sql` / `bq406` (GOOGLE_DEI): `'No schema snapshot registered for db_id=google_dei'`
- `spider-lite-sql` / `bq407` (COVID19_USA): `'No schema snapshot registered for db_id=covid19_usa'`
- `spider-lite-sql` / `bq413` (DIMENSIONS_AI_COVID19): `'No schema snapshot registered for db_id=dimensions_ai_covid19'`
- `spider-lite-sql` / `bq414` (THE_MET): `'No schema snapshot registered for db_id=the_met'`
- `spider-lite-sql` / `bq418` (TARGETOME_REACTOME): `'No schema snapshot registered for db_id=targetome_reactome'`
- `spider-lite-sql` / `bq419` (NOAA_DATA): `'No schema snapshot registered for db_id=noaa_data'`
- `spider-lite-sql` / `bq424` (WORLD_BANK): `'No schema snapshot registered for db_id=world_bank'`
- `spider-lite-sql` / `bq425` (EBI_CHEMBL): `'No schema snapshot registered for db_id=ebi_chembl'`
- `spider-lite-sql` / `bq427` (NCAA_BASKETBALL): `'No schema snapshot registered for db_id=ncaa_basketball'`
- `spider-lite-sql` / `bq428` (NCAA_BASKETBALL): `'No schema snapshot registered for db_id=ncaa_basketball'`
- `spider-lite-sql` / `bq430` (EBI_CHEMBL): `'No schema snapshot registered for db_id=ebi_chembl'`
- `spider-lite-sql` / `bq432` (FDA): `'No schema snapshot registered for db_id=fda'`
- `spider-lite-sql` / `bq441` (NHTSA_TRAFFIC_FATALITIES): `'No schema snapshot registered for db_id=nhtsa_traffic_fatalities'`
- `spider-lite-sql` / `bq442` (CYMBAL_INVESTMENTS): `'No schema snapshot registered for db_id=CYMBAL_INVESTMENTS'`
- `spider-lite-sql` / `bq445` (GNOMAD): `'No schema snapshot registered for db_id=gnomAD'`
- `spider-lite-sql` / `bq457` (LIBRARIES_IO): `'No schema snapshot registered for db_id=libraries_io'`
- `spider-lite-sql` / `bq461` (NCAA_BASKETBALL): `'No schema snapshot registered for db_id=ncaa_basketball'`
- `spider-lite-sql` / `bq462` (NCAA_BASKETBALL): `'No schema snapshot registered for db_id=ncaa_basketball'`
- `spider-lite-sql` / `ga001` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `spider-lite-sql` / `ga002` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `spider-lite-sql` / `ga003` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `spider-lite-sql` / `ga004` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `spider-lite-sql` / `ga005` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `spider-lite-sql` / `ga006` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `spider-lite-sql` / `ga007` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `spider-lite-sql` / `ga008` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `spider-lite-sql` / `ga009` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `spider-lite-sql` / `ga010` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `spider-lite-sql` / `ga011` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `spider-lite-sql` / `ga012` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `spider-lite-sql` / `ga013` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `spider-lite-sql` / `ga014` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `spider-lite-sql` / `ga017` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `spider-lite-sql` / `ga018` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `spider-lite-sql` / `ga019` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `spider-lite-sql` / `ga020` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `spider-lite-sql` / `ga021` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `spider-lite-sql` / `ga022` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `spider-lite-sql` / `ga025` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `spider-lite-sql` / `ga028` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `spider-lite-sql` / `ga030` (FIREBASE): `'No schema snapshot registered for db_id=firebase'`
- `spider-lite-sql` / `ga031` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `spider-lite-sql` / `ga032` (GA4): `'No schema snapshot registered for db_id=ga4'`
- `spider-lite-sql` / `local002` (E_COMMERCE): `'No schema snapshot registered for db_id=E_commerce'`
- `spider-lite-sql` / `local003` (E_COMMERCE): `'No schema snapshot registered for db_id=E_commerce'`
- `spider-lite-sql` / `local004` (E_COMMERCE): `'No schema snapshot registered for db_id=E_commerce'`
- `spider-lite-sql` / `local007` (BASEBALL): `'No schema snapshot registered for db_id=Baseball'`
- `spider-lite-sql` / `local008` (BASEBALL): `'No schema snapshot registered for db_id=Baseball'`
- `spider-lite-sql` / `local009` (AIRLINES): `'No schema snapshot registered for db_id=Airlines'`
- `spider-lite-sql` / `local010` (AIRLINES): `'No schema snapshot registered for db_id=Airlines'`
- `spider-lite-sql` / `local015` (CALIFORNIA_TRAFFIC_COLLISION): `'No schema snapshot registered for db_id=California_Traffic_Collision'`
- `spider-lite-sql` / `local017` (CALIFORNIA_TRAFFIC_COLLISION): `'No schema snapshot registered for db_id=California_Traffic_Collision'`
- `spider-lite-sql` / `local018` (CALIFORNIA_TRAFFIC_COLLISION): `'No schema snapshot registered for db_id=California_Traffic_Collision'`
- `spider-lite-sql` / `local019` (WWE): `'No schema snapshot registered for db_id=WWE'`
- `spider-lite-sql` / `local020` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `spider-lite-sql` / `local021` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `spider-lite-sql` / `local022` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `spider-lite-sql` / `local023` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `spider-lite-sql` / `local024` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `spider-lite-sql` / `local025` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `spider-lite-sql` / `local026` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `spider-lite-sql` / `local028` (BRAZILIAN_E_COMMERCE): `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`
- `spider-lite-sql` / `local029` (BRAZILIAN_E_COMMERCE): `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`
- `spider-lite-sql` / `local030` (BRAZILIAN_E_COMMERCE): `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`
- `spider-lite-sql` / `local031` (BRAZILIAN_E_COMMERCE): `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`
- `spider-lite-sql` / `local032` (BRAZILIAN_E_COMMERCE): `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`
- `spider-lite-sql` / `local034` (BRAZILIAN_E_COMMERCE): `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`
- `spider-lite-sql` / `local035` (BRAZILIAN_E_COMMERCE): `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`
- `spider-lite-sql` / `local037` (BRAZILIAN_E_COMMERCE): `'No schema snapshot registered for db_id=Brazilian_E_Commerce'`
- `spider-lite-sql` / `local040` (MODERN_DATA): `'No schema snapshot registered for db_id=modern_data'`
- `spider-lite-sql` / `local041` (MODERN_DATA): `'No schema snapshot registered for db_id=modern_data'`
- `spider-lite-sql` / `local049` (MODERN_DATA): `'No schema snapshot registered for db_id=modern_data'`
- `spider-lite-sql` / `local050` (COMPLEX_ORACLE): `'No schema snapshot registered for db_id=complex_oracle'`
- `spider-lite-sql` / `local058` (EDUCATION_BUSINESS): `'No schema snapshot registered for db_id=education_business'`
- `spider-lite-sql` / `local059` (EDUCATION_BUSINESS): `'No schema snapshot registered for db_id=education_business'`
- `spider-lite-sql` / `local060` (COMPLEX_ORACLE): `'No schema snapshot registered for db_id=complex_oracle'`
- `spider-lite-sql` / `local061` (COMPLEX_ORACLE): `'No schema snapshot registered for db_id=complex_oracle'`
- `spider-lite-sql` / `local062` (COMPLEX_ORACLE): `'No schema snapshot registered for db_id=complex_oracle'`
- `spider-lite-sql` / `local063` (COMPLEX_ORACLE): `'No schema snapshot registered for db_id=complex_oracle'`
- `spider-lite-sql` / `local064` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `spider-lite-sql` / `local065` (MODERN_DATA): `'No schema snapshot registered for db_id=modern_data'`
- `spider-lite-sql` / `local066` (MODERN_DATA): `'No schema snapshot registered for db_id=modern_data'`
- `spider-lite-sql` / `local067` (COMPLEX_ORACLE): `'No schema snapshot registered for db_id=complex_oracle'`
- `spider-lite-sql` / `local068` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `spider-lite-sql` / `local070` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `spider-lite-sql` / `local071` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `spider-lite-sql` / `local072` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `spider-lite-sql` / `local073` (MODERN_DATA): `'No schema snapshot registered for db_id=modern_data'`
- `spider-lite-sql` / `local074` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `spider-lite-sql` / `local075` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `spider-lite-sql` / `local077` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `spider-lite-sql` / `local078` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `spider-lite-sql` / `local081` (NORTHWIND): `'No schema snapshot registered for db_id=northwind'`
- `spider-lite-sql` / `local085` (NORTHWIND): `'No schema snapshot registered for db_id=northwind'`
- `spider-lite-sql` / `local096` (DB-IMDB): `'No schema snapshot registered for db_id=Db-IMDB'`
- `spider-lite-sql` / `local097` (DB-IMDB): `'No schema snapshot registered for db_id=Db-IMDB'`
- `spider-lite-sql` / `local098` (DB-IMDB): `'No schema snapshot registered for db_id=Db-IMDB'`
- `spider-lite-sql` / `local099` (DB-IMDB): `'No schema snapshot registered for db_id=Db-IMDB'`
- `spider-lite-sql` / `local100` (DB-IMDB): `'No schema snapshot registered for db_id=Db-IMDB'`
- `spider-lite-sql` / `local114` (EDUCATION_BUSINESS): `'No schema snapshot registered for db_id=education_business'`
- `spider-lite-sql` / `local128` (BOWLINGLEAGUE): `'No schema snapshot registered for db_id=BowlingLeague'`
- `spider-lite-sql` / `local130` (SCHOOL_SCHEDULING): `'No schema snapshot registered for db_id=school_scheduling'`
- `spider-lite-sql` / `local131` (ENTERTAINMENTAGENCY): `'No schema snapshot registered for db_id=EntertainmentAgency'`
- `spider-lite-sql` / `local132` (ENTERTAINMENTAGENCY): `'No schema snapshot registered for db_id=EntertainmentAgency'`
- `spider-lite-sql` / `local133` (ENTERTAINMENTAGENCY): `'No schema snapshot registered for db_id=EntertainmentAgency'`
- `spider-lite-sql` / `local141` (ADVENTUREWORKS): `'No schema snapshot registered for db_id=AdventureWorks'`
- `spider-lite-sql` / `local152` (IMDB_MOVIES): `'No schema snapshot registered for db_id=imdb_movies'`
- `spider-lite-sql` / `local156` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `spider-lite-sql` / `local157` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `spider-lite-sql` / `local163` (EDUCATION_BUSINESS): `'No schema snapshot registered for db_id=education_business'`
- `spider-lite-sql` / `local167` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `spider-lite-sql` / `local168` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `spider-lite-sql` / `local169` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `spider-lite-sql` / `local170` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `spider-lite-sql` / `local171` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `spider-lite-sql` / `local201` (MODERN_DATA): `'No schema snapshot registered for db_id=modern_data'`
- `spider-lite-sql` / `local202` (CITY_LEGISLATION): `'No schema snapshot registered for db_id=city_legislation'`
- `spider-lite-sql` / `local209` (DELIVERY_CENTER): `'No schema snapshot registered for db_id=delivery_center'`
- `spider-lite-sql` / `local210` (DELIVERY_CENTER): `'No schema snapshot registered for db_id=delivery_center'`
- `spider-lite-sql` / `local212` (DELIVERY_CENTER): `'No schema snapshot registered for db_id=delivery_center'`
- `spider-lite-sql` / `local218` (EU_SOCCER): `'No schema snapshot registered for db_id=EU_soccer'`
- `spider-lite-sql` / `local219` (EU_SOCCER): `'No schema snapshot registered for db_id=EU_soccer'`
- `spider-lite-sql` / `local220` (EU_SOCCER): `'No schema snapshot registered for db_id=EU_soccer'`
- `spider-lite-sql` / `local221` (EU_SOCCER): `'No schema snapshot registered for db_id=EU_soccer'`
- `spider-lite-sql` / `local228` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `spider-lite-sql` / `local229` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `spider-lite-sql` / `local230` (IMDB_MOVIES): `'No schema snapshot registered for db_id=imdb_movies'`
- `spider-lite-sql` / `local244` (MUSIC): `'No schema snapshot registered for db_id=music'`
- `spider-lite-sql` / `local253` (EDUCATION_BUSINESS): `'No schema snapshot registered for db_id=education_business'`
- `spider-lite-sql` / `local258` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `spider-lite-sql` / `local259` (IPL): `'No schema snapshot registered for db_id=IPL'`
- `spider-lite-sql` / `local262` (STACKING): `'No schema snapshot registered for db_id=stacking'`
- `spider-lite-sql` / `local263` (STACKING): `'No schema snapshot registered for db_id=stacking'`
- `spider-lite-sql` / `local264` (STACKING): `'No schema snapshot registered for db_id=stacking'`
- `spider-lite-sql` / `local269` (ORACLE_SQL): `'No schema snapshot registered for db_id=oracle_sql'`
- `spider-lite-sql` / `local270` (ORACLE_SQL): `'No schema snapshot registered for db_id=oracle_sql'`
- `spider-lite-sql` / `local272` (ORACLE_SQL): `'No schema snapshot registered for db_id=oracle_sql'`
- `spider-lite-sql` / `local273` (ORACLE_SQL): `'No schema snapshot registered for db_id=oracle_sql'`
- `spider-lite-sql` / `local274` (ORACLE_SQL): `'No schema snapshot registered for db_id=oracle_sql'`
- `spider-lite-sql` / `local275` (ORACLE_SQL): `'No schema snapshot registered for db_id=oracle_sql'`
- `spider-lite-sql` / `local277` (ORACLE_SQL): `'No schema snapshot registered for db_id=oracle_sql'`
- `spider-lite-sql` / `local279` (ORACLE_SQL): `'No schema snapshot registered for db_id=oracle_sql'`
- `spider-lite-sql` / `local283` (EU_SOCCER): `'No schema snapshot registered for db_id=EU_soccer'`
- `spider-lite-sql` / `local284` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `spider-lite-sql` / `local285` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `spider-lite-sql` / `local286` (ELECTRONIC_SALES): `'No schema snapshot registered for db_id=electronic_sales'`
- `spider-lite-sql` / `local297` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `spider-lite-sql` / `local298` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `spider-lite-sql` / `local299` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `spider-lite-sql` / `local300` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `spider-lite-sql` / `local301` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `spider-lite-sql` / `local302` (BANK_SALES_TRADING): `'No schema snapshot registered for db_id=bank_sales_trading'`
- `spider-lite-sql` / `local309` (F1): `'No schema snapshot registered for db_id=f1'`
- `spider-lite-sql` / `local310` (F1): `'No schema snapshot registered for db_id=f1'`
- `spider-lite-sql` / `local311` (F1): `'No schema snapshot registered for db_id=f1'`
- `spider-lite-sql` / `local329` (LOG): `'No schema snapshot registered for db_id=log'`
- `spider-lite-sql` / `local330` (LOG): `'No schema snapshot registered for db_id=log'`
- `spider-lite-sql` / `local331` (LOG): `'No schema snapshot registered for db_id=log'`
- `spider-lite-sql` / `local335` (F1): `'No schema snapshot registered for db_id=f1'`
- `spider-lite-sql` / `local336` (F1): `'No schema snapshot registered for db_id=f1'`
- `spider-lite-sql` / `local344` (F1): `'No schema snapshot registered for db_id=f1'`
- `spider-lite-sql` / `local354` (F1): `'No schema snapshot registered for db_id=f1'`
- `spider-lite-sql` / `local355` (F1): `'No schema snapshot registered for db_id=f1'`
- `spider-lite-sql` / `local356` (F1): `'No schema snapshot registered for db_id=f1'`
- `spider-lite-sql` / `local358` (LOG): `'No schema snapshot registered for db_id=log'`
- `spider-lite-sql` / `local360` (LOG): `'No schema snapshot registered for db_id=log'`
- `spider-lite-sql` / `sf001` (GLOBAL_WEATHER__CLIMATE_DATA_FOR_BI): `'No schema snapshot registered for db_id=GLOBAL_WEATHER__CLIMATE_DATA_FOR_BI'`
- `spider-lite-sql` / `sf002` (FINANCE__ECONOMICS): `'No schema snapshot registered for db_id=FINANCE__ECONOMICS'`
- `spider-lite-sql` / `sf003` (GLOBAL_GOVERNMENT): `'No schema snapshot registered for db_id=GLOBAL_GOVERNMENT'`
- `spider-lite-sql` / `sf006` (FINANCE__ECONOMICS): `'No schema snapshot registered for db_id=FINANCE__ECONOMICS'`
- `spider-lite-sql` / `sf008` (US_REAL_ESTATE): `'No schema snapshot registered for db_id=US_REAL_ESTATE'`
- `spider-lite-sql` / `sf009` (NETHERLANDS_OPEN_MAP_DATA): `'No schema snapshot registered for db_id=NETHERLANDS_OPEN_MAP_DATA'`
- `spider-lite-sql` / `sf010` (US_REAL_ESTATE): `'No schema snapshot registered for db_id=US_REAL_ESTATE'`
- `spider-lite-sql` / `sf011` (CENSUS_GALAXY__ZIP_CODE_TO_BLOCK_GROUP_SAMPLE): `'No schema snapshot registered for db_id=CENSUS_GALAXY__ZIP_CODE_TO_BLOCK_GROUP_SAMPLE'`
- `spider-lite-sql` / `sf012` (WEATHER__ENVIRONMENT): `'No schema snapshot registered for db_id=WEATHER__ENVIRONMENT'`
- `spider-lite-sql` / `sf013` (NETHERLANDS_OPEN_MAP_DATA): `'No schema snapshot registered for db_id=NETHERLANDS_OPEN_MAP_DATA'`
- `spider-lite-sql` / `sf014` (CENSUS_GALAXY__AIML_MODEL_DATA_ENRICHMENT_SAMPLE): `'No schema snapshot registered for db_id=CENSUS_GALAXY__AIML_MODEL_DATA_ENRICHMENT_SAMPLE'`
- `spider-lite-sql` / `sf018` (BRAZE_USER_EVENT_DEMO_DATASET): `'No schema snapshot registered for db_id=BRAZE_USER_EVENT_DEMO_DATASET'`
- `spider-lite-sql` / `sf029` (AMAZON_VENDOR_ANALYTICS__SAMPLE_DATASET): `'No schema snapshot registered for db_id=AMAZON_VENDOR_ANALYTICS__SAMPLE_DATASET'`
- `spider-lite-sql` / `sf035` (BRAZE_USER_EVENT_DEMO_DATASET): `'No schema snapshot registered for db_id=BRAZE_USER_EVENT_DEMO_DATASET'`
- `spider-lite-sql` / `sf037` (US_REAL_ESTATE): `'No schema snapshot registered for db_id=US_REAL_ESTATE'`
- `spider-lite-sql` / `sf040` (US_ADDRESSES__POI): `'No schema snapshot registered for db_id=US_ADDRESSES__POI'`
- `spider-lite-sql` / `sf041` (YES_ENERGY__SAMPLE_DATA): `'No schema snapshot registered for db_id=YES_ENERGY__SAMPLE_DATA'`
- `spider-lite-sql` / `sf044` (FINANCE__ECONOMICS): `'No schema snapshot registered for db_id=FINANCE__ECONOMICS'`
- `spider-lite-sql` / `sf_bq005` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq007` (CENSUS_BUREAU_ACS_2): `'No schema snapshot registered for db_id=CENSUS_BUREAU_ACS_2'`
- `spider-lite-sql` / `sf_bq012` (ETHEREUM_BLOCKCHAIN): `'No schema snapshot registered for db_id=ETHEREUM_BLOCKCHAIN'`
- `spider-lite-sql` / `sf_bq014` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq015` (STACKOVERFLOW_PLUS): `'No schema snapshot registered for db_id=STACKOVERFLOW_PLUS'`
- `spider-lite-sql` / `sf_bq016` (DEPS_DEV_V1): `'No schema snapshot registered for db_id=DEPS_DEV_V1'`
- `spider-lite-sql` / `sf_bq017` (GEO_OPENSTREETMAP): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP'`
- `spider-lite-sql` / `sf_bq020` (GENOMICS_CANNABIS): `'No schema snapshot registered for db_id=GENOMICS_CANNABIS'`
- `spider-lite-sql` / `sf_bq026` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `spider-lite-sql` / `sf_bq027` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `spider-lite-sql` / `sf_bq028` (DEPS_DEV_V1): `'No schema snapshot registered for db_id=DEPS_DEV_V1'`
- `spider-lite-sql` / `sf_bq029` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `spider-lite-sql` / `sf_bq033` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `spider-lite-sql` / `sf_bq036` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `spider-lite-sql` / `sf_bq037` (HUMAN_GENOME_VARIANTS): `'No schema snapshot registered for db_id=HUMAN_GENOME_VARIANTS'`
- `spider-lite-sql` / `sf_bq043` (TCGA): `'No schema snapshot registered for db_id=TCGA'`
- `spider-lite-sql` / `sf_bq044` (TCGA): `'No schema snapshot registered for db_id=TCGA'`
- `spider-lite-sql` / `sf_bq050` (NEW_YORK_CITIBIKE_1): `'No schema snapshot registered for db_id=NEW_YORK_CITIBIKE_1'`
- `spider-lite-sql` / `sf_bq052` (PATENTSVIEW): `'No schema snapshot registered for db_id=PATENTSVIEW'`
- `spider-lite-sql` / `sf_bq056` (GEO_OPENSTREETMAP_BOUNDARIES): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP_BOUNDARIES'`
- `spider-lite-sql` / `sf_bq057` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq058` (GOOG_BLOCKCHAIN): `'No schema snapshot registered for db_id=GOOG_BLOCKCHAIN'`
- `spider-lite-sql` / `sf_bq062` (DEPS_DEV_V1): `'No schema snapshot registered for db_id=DEPS_DEV_V1'`
- `spider-lite-sql` / `sf_bq063` (DEPS_DEV_V1): `'No schema snapshot registered for db_id=DEPS_DEV_V1'`
- `spider-lite-sql` / `sf_bq065` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq068` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq069` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `spider-lite-sql` / `sf_bq070` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `spider-lite-sql` / `sf_bq071` (NOAA_DATA_PLUS): `'No schema snapshot registered for db_id=NOAA_DATA_PLUS'`
- `spider-lite-sql` / `sf_bq072` (DEATH): `'No schema snapshot registered for db_id=DEATH'`
- `spider-lite-sql` / `sf_bq073` (CENSUS_BUREAU_ACS_2): `'No schema snapshot registered for db_id=CENSUS_BUREAU_ACS_2'`
- `spider-lite-sql` / `sf_bq078` (OPEN_TARGETS_PLATFORM_2): `'No schema snapshot registered for db_id=OPEN_TARGETS_PLATFORM_2'`
- `spider-lite-sql` / `sf_bq080` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq083` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq084` (GOOG_BLOCKCHAIN): `'No schema snapshot registered for db_id=GOOG_BLOCKCHAIN'`
- `spider-lite-sql` / `sf_bq091` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `spider-lite-sql` / `sf_bq092` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq093` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq095` (OPEN_TARGETS_PLATFORM_1): `'No schema snapshot registered for db_id=OPEN_TARGETS_PLATFORM_1'`
- `spider-lite-sql` / `sf_bq099` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `spider-lite-sql` / `sf_bq100` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `spider-lite-sql` / `sf_bq101` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `spider-lite-sql` / `sf_bq104` (GOOGLE_TRENDS): `'No schema snapshot registered for db_id=GOOGLE_TRENDS'`
- `spider-lite-sql` / `sf_bq107` (GENOMICS_CANNABIS): `'No schema snapshot registered for db_id=GENOMICS_CANNABIS'`
- `spider-lite-sql` / `sf_bq117` (NOAA_DATA): `'No schema snapshot registered for db_id=NOAA_DATA'`
- `spider-lite-sql` / `sf_bq118` (DEATH): `'No schema snapshot registered for db_id=DEATH'`
- `spider-lite-sql` / `sf_bq121` (STACKOVERFLOW): `'No schema snapshot registered for db_id=STACKOVERFLOW'`
- `spider-lite-sql` / `sf_bq127` (PATENTS_GOOGLE): `'No schema snapshot registered for db_id=PATENTS_GOOGLE'`
- `spider-lite-sql` / `sf_bq128` (PATENTSVIEW): `'No schema snapshot registered for db_id=PATENTSVIEW'`
- `spider-lite-sql` / `sf_bq131` (GEO_OPENSTREETMAP): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP'`
- `spider-lite-sql` / `sf_bq135` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq136` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq141` (TCGA_HG38_DATA_V0): `'No schema snapshot registered for db_id=TCGA_HG38_DATA_V0'`
- `spider-lite-sql` / `sf_bq147` (TCGA): `'No schema snapshot registered for db_id=TCGA'`
- `spider-lite-sql` / `sf_bq148` (TCGA): `'No schema snapshot registered for db_id=TCGA'`
- `spider-lite-sql` / `sf_bq150` (TCGA_HG19_DATA_V0): `'No schema snapshot registered for db_id=TCGA_HG19_DATA_V0'`
- `spider-lite-sql` / `sf_bq152` (TCGA_HG38_DATA_V0): `'No schema snapshot registered for db_id=TCGA_HG38_DATA_V0'`
- `spider-lite-sql` / `sf_bq153` (PANCANCER_ATLAS_1): `'No schema snapshot registered for db_id=PANCANCER_ATLAS_1'`
- `spider-lite-sql` / `sf_bq154` (PANCANCER_ATLAS_1): `'No schema snapshot registered for db_id=PANCANCER_ATLAS_1'`
- `spider-lite-sql` / `sf_bq155` (TCGA_HG38_DATA_V0): `'No schema snapshot registered for db_id=TCGA_HG38_DATA_V0'`
- `spider-lite-sql` / `sf_bq156` (PANCANCER_ATLAS_1): `'No schema snapshot registered for db_id=PANCANCER_ATLAS_1'`
- `spider-lite-sql` / `sf_bq157` (PANCANCER_ATLAS_1): `'No schema snapshot registered for db_id=PANCANCER_ATLAS_1'`
- `spider-lite-sql` / `sf_bq158` (PANCANCER_ATLAS_1): `'No schema snapshot registered for db_id=PANCANCER_ATLAS_1'`
- `spider-lite-sql` / `sf_bq159` (PANCANCER_ATLAS_1): `'No schema snapshot registered for db_id=PANCANCER_ATLAS_1'`
- `spider-lite-sql` / `sf_bq160` (META_KAGGLE): `'No schema snapshot registered for db_id=META_KAGGLE'`
- `spider-lite-sql` / `sf_bq163` (HTAN_2): `'No schema snapshot registered for db_id=HTAN_2'`
- `spider-lite-sql` / `sf_bq164` (HTAN_2): `'No schema snapshot registered for db_id=HTAN_2'`
- `spider-lite-sql` / `sf_bq166` (TCGA_MITELMAN): `'No schema snapshot registered for db_id=TCGA_MITELMAN'`
- `spider-lite-sql` / `sf_bq167` (META_KAGGLE): `'No schema snapshot registered for db_id=META_KAGGLE'`
- `spider-lite-sql` / `sf_bq170` (TCGA_MITELMAN): `'No schema snapshot registered for db_id=TCGA_MITELMAN'`
- `spider-lite-sql` / `sf_bq171` (META_KAGGLE): `'No schema snapshot registered for db_id=META_KAGGLE'`
- `spider-lite-sql` / `sf_bq175` (TCGA_MITELMAN): `'No schema snapshot registered for db_id=TCGA_MITELMAN'`
- `spider-lite-sql` / `sf_bq176` (TCGA_MITELMAN): `'No schema snapshot registered for db_id=TCGA_MITELMAN'`
- `spider-lite-sql` / `sf_bq180` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `spider-lite-sql` / `sf_bq182` (GITHUB_REPOS_DATE): `'No schema snapshot registered for db_id=GITHUB_REPOS_DATE'`
- `spider-lite-sql` / `sf_bq184` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq187` (ETHEREUM_BLOCKCHAIN): `'No schema snapshot registered for db_id=ETHEREUM_BLOCKCHAIN'`
- `spider-lite-sql` / `sf_bq188` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq189` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq190` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq191` (GITHUB_REPOS_DATE): `'No schema snapshot registered for db_id=GITHUB_REPOS_DATE'`
- `spider-lite-sql` / `sf_bq192` (GITHUB_REPOS_DATE): `'No schema snapshot registered for db_id=GITHUB_REPOS_DATE'`
- `spider-lite-sql` / `sf_bq193` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `spider-lite-sql` / `sf_bq194` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `spider-lite-sql` / `sf_bq195` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq197` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq207` (PATENTS_USPTO): `'No schema snapshot registered for db_id=PATENTS_USPTO'`
- `spider-lite-sql` / `sf_bq209` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `spider-lite-sql` / `sf_bq210` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `spider-lite-sql` / `sf_bq211` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `spider-lite-sql` / `sf_bq212` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `spider-lite-sql` / `sf_bq213` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `spider-lite-sql` / `sf_bq214` (PATENTS_GOOGLE): `'No schema snapshot registered for db_id=PATENTS_GOOGLE'`
- `spider-lite-sql` / `sf_bq215` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `spider-lite-sql` / `sf_bq216` (PATENTS_GOOGLE): `'No schema snapshot registered for db_id=PATENTS_GOOGLE'`
- `spider-lite-sql` / `sf_bq217` (GITHUB_REPOS_DATE): `'No schema snapshot registered for db_id=GITHUB_REPOS_DATE'`
- `spider-lite-sql` / `sf_bq219` (IOWA_LIQUOR_SALES): `'No schema snapshot registered for db_id=IOWA_LIQUOR_SALES'`
- `spider-lite-sql` / `sf_bq221` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `spider-lite-sql` / `sf_bq222` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `spider-lite-sql` / `sf_bq223` (PATENTS): `'No schema snapshot registered for db_id=PATENTS'`
- `spider-lite-sql` / `sf_bq224` (GITHUB_REPOS_DATE): `'No schema snapshot registered for db_id=GITHUB_REPOS_DATE'`
- `spider-lite-sql` / `sf_bq225` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `spider-lite-sql` / `sf_bq226` (GOOG_BLOCKCHAIN): `'No schema snapshot registered for db_id=GOOG_BLOCKCHAIN'`
- `spider-lite-sql` / `sf_bq233` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `spider-lite-sql` / `sf_bq236` (NOAA_DATA_PLUS): `'No schema snapshot registered for db_id=NOAA_DATA_PLUS'`
- `spider-lite-sql` / `sf_bq246` (PATENTSVIEW): `'No schema snapshot registered for db_id=PATENTSVIEW'`
- `spider-lite-sql` / `sf_bq247` (PATENTS_GOOGLE): `'No schema snapshot registered for db_id=PATENTS_GOOGLE'`
- `spider-lite-sql` / `sf_bq248` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `spider-lite-sql` / `sf_bq249` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `spider-lite-sql` / `sf_bq250` (GEO_OPENSTREETMAP_WORLDPOP): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP_WORLDPOP'`
- `spider-lite-sql` / `sf_bq251` (PYPI): `'No schema snapshot registered for db_id=PYPI'`
- `spider-lite-sql` / `sf_bq252` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `spider-lite-sql` / `sf_bq253` (GEO_OPENSTREETMAP): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP'`
- `spider-lite-sql` / `sf_bq254` (GEO_OPENSTREETMAP): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP'`
- `spider-lite-sql` / `sf_bq255` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `spider-lite-sql` / `sf_bq256` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq258` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq259` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq260` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq261` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq262` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq263` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq264` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq265` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq266` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq271` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq272` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq273` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq276` (NOAA_PORTS): `'No schema snapshot registered for db_id=NOAA_PORTS'`
- `spider-lite-sql` / `sf_bq283` (AUSTIN): `'No schema snapshot registered for db_id=AUSTIN'`
- `spider-lite-sql` / `sf_bq289` (GEO_OPENSTREETMAP_CENSUS_PLACES): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP_CENSUS_PLACES'`
- `spider-lite-sql` / `sf_bq291` (NOAA_GLOBAL_FORECAST_SYSTEM): `'No schema snapshot registered for db_id=NOAA_GLOBAL_FORECAST_SYSTEM'`
- `spider-lite-sql` / `sf_bq292` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq294` (SAN_FRANCISCO_PLUS): `'No schema snapshot registered for db_id=SAN_FRANCISCO_PLUS'`
- `spider-lite-sql` / `sf_bq295` (GITHUB_REPOS_DATE): `'No schema snapshot registered for db_id=GITHUB_REPOS_DATE'`
- `spider-lite-sql` / `sf_bq307` (STACKOVERFLOW): `'No schema snapshot registered for db_id=STACKOVERFLOW'`
- `spider-lite-sql` / `sf_bq320` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `spider-lite-sql` / `sf_bq321` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `spider-lite-sql` / `sf_bq323` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `spider-lite-sql` / `sf_bq324` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `spider-lite-sql` / `sf_bq325` (OPEN_TARGETS_GENETICS_2): `'No schema snapshot registered for db_id=OPEN_TARGETS_GENETICS_2'`
- `spider-lite-sql` / `sf_bq331` (META_KAGGLE): `'No schema snapshot registered for db_id=META_KAGGLE'`
- `spider-lite-sql` / `sf_bq333` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq334` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq335` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq340` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq341` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq342` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq345` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `spider-lite-sql` / `sf_bq346` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `spider-lite-sql` / `sf_bq347` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `spider-lite-sql` / `sf_bq348` (GEO_OPENSTREETMAP): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP'`
- `spider-lite-sql` / `sf_bq349` (GEO_OPENSTREETMAP): `'No schema snapshot registered for db_id=GEO_OPENSTREETMAP'`
- `spider-lite-sql` / `sf_bq350` (OPEN_TARGETS_PLATFORM_1): `'No schema snapshot registered for db_id=OPEN_TARGETS_PLATFORM_1'`
- `spider-lite-sql` / `sf_bq358` (NEW_YORK_CITIBIKE_1): `'No schema snapshot registered for db_id=NEW_YORK_CITIBIKE_1'`
- `spider-lite-sql` / `sf_bq359` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `spider-lite-sql` / `sf_bq361` (THELOOK_ECOMMERCE): `'No schema snapshot registered for db_id=THELOOK_ECOMMERCE'`
- `spider-lite-sql` / `sf_bq370` (WIDE_WORLD_IMPORTERS): `'No schema snapshot registered for db_id=WIDE_WORLD_IMPORTERS'`
- `spider-lite-sql` / `sf_bq371` (WIDE_WORLD_IMPORTERS): `'No schema snapshot registered for db_id=WIDE_WORLD_IMPORTERS'`
- `spider-lite-sql` / `sf_bq372` (WIDE_WORLD_IMPORTERS): `'No schema snapshot registered for db_id=WIDE_WORLD_IMPORTERS'`
- `spider-lite-sql` / `sf_bq373` (WIDE_WORLD_IMPORTERS): `'No schema snapshot registered for db_id=WIDE_WORLD_IMPORTERS'`
- `spider-lite-sql` / `sf_bq375` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `spider-lite-sql` / `sf_bq377` (GITHUB_REPOS): `'No schema snapshot registered for db_id=GITHUB_REPOS'`
- `spider-lite-sql` / `sf_bq379` (OPEN_TARGETS_PLATFORM_1): `'No schema snapshot registered for db_id=OPEN_TARGETS_PLATFORM_1'`
- `spider-lite-sql` / `sf_bq380` (META_KAGGLE): `'No schema snapshot registered for db_id=META_KAGGLE'`
- `spider-lite-sql` / `sf_bq390` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `spider-lite-sql` / `sf_bq410` (CENSUS_BUREAU_ACS_2): `'No schema snapshot registered for db_id=CENSUS_BUREAU_ACS_2'`
- `spider-lite-sql` / `sf_bq411` (GOOGLE_TRENDS): `'No schema snapshot registered for db_id=GOOGLE_TRENDS'`
- `spider-lite-sql` / `sf_bq412` (GOOGLE_ADS): `'No schema snapshot registered for db_id=GOOGLE_ADS'`
- `spider-lite-sql` / `sf_bq415` (HUMAN_GENOME_VARIANTS): `'No schema snapshot registered for db_id=HUMAN_GENOME_VARIANTS'`
- `spider-lite-sql` / `sf_bq416` (GOOG_BLOCKCHAIN): `'No schema snapshot registered for db_id=GOOG_BLOCKCHAIN'`
- `spider-lite-sql` / `sf_bq417` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `spider-lite-sql` / `sf_bq420` (PATENTS_USPTO): `'No schema snapshot registered for db_id=PATENTS_USPTO'`
- `spider-lite-sql` / `sf_bq421` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `spider-lite-sql` / `sf_bq422` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `spider-lite-sql` / `sf_bq423` (GOOGLE_ADS): `'No schema snapshot registered for db_id=GOOGLE_ADS'`
- `spider-lite-sql` / `sf_bq426` (NEW_YORK_CITIBIKE_1): `'No schema snapshot registered for db_id=NEW_YORK_CITIBIKE_1'`
- `spider-lite-sql` / `sf_bq429` (CENSUS_BUREAU_ACS_2): `'No schema snapshot registered for db_id=CENSUS_BUREAU_ACS_2'`
- `spider-lite-sql` / `sf_bq444` (CRYPTO): `'No schema snapshot registered for db_id=CRYPTO'`
- `spider-lite-sql` / `sf_bq450` (ETHEREUM_BLOCKCHAIN): `'No schema snapshot registered for db_id=ETHEREUM_BLOCKCHAIN'`
- `spider-lite-sql` / `sf_bq451` (_1000_GENOMES): `'No schema snapshot registered for db_id=_1000_GENOMES'`
- `spider-lite-sql` / `sf_bq452` (_1000_GENOMES): `'No schema snapshot registered for db_id=_1000_GENOMES'`
- `spider-lite-sql` / `sf_bq453` (_1000_GENOMES): `'No schema snapshot registered for db_id=_1000_GENOMES'`
- `spider-lite-sql` / `sf_bq454` (_1000_GENOMES): `'No schema snapshot registered for db_id=_1000_GENOMES'`
- `spider-lite-sql` / `sf_bq455` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `spider-lite-sql` / `sf_bq456` (IDC): `'No schema snapshot registered for db_id=IDC'`
- `spider-lite-sql` / `sf_bq458` (WORD_VECTORS_US): `'No schema snapshot registered for db_id=WORD_VECTORS_US'`
- `spider-lite-sql` / `sf_bq459` (WORD_VECTORS_US): `'No schema snapshot registered for db_id=WORD_VECTORS_US'`
- `spider-lite-sql` / `sf_bq460` (WORD_VECTORS_US): `'No schema snapshot registered for db_id=WORD_VECTORS_US'`
- `spider-snow-sql` / `sf001` (GLOBAL_WEATHER__CLIMATE_DATA_FOR_BI): `002003 (02000): SQL compilation error:`
- `spider-snow-sql` / `sf009` (NETHERLANDS_OPEN_MAP_DATA): `003030 (02000): SQL compilation error:`
- `spider-snow-sql` / `sf013` (NETHERLANDS_OPEN_MAP_DATA): `003030 (02000): SQL compilation error:`
- `spider-snow-sql` / `sf029` (AMAZON_VENDOR_ANALYTICS__SAMPLE_DATASET): `003030 (02000): SQL compilation error:`
- `spider-snow-sql` / `sf_local007` (BASEBALL): `000904 (42000): SQL compilation error: error line 3 at position 32`
- `spider-snow-sql` / `sf_local008` (BASEBALL): `000904 (42000): SQL compilation error: error line 3 at position 8`
- `spider-snow-sql` / `sf_local032` (BRAZILIAN_E_COMMERCE): `000904 (42000): SQL compilation error: error line 50 at position 97`

All wrong-but-executed task IDs:
- `spider-snow-sql` / `sf002` (FINANCE__ECONOMICS)
- `spider-snow-sql` / `sf003` (GLOBAL_GOVERNMENT)
- `spider-snow-sql` / `sf006` (FINANCE__ECONOMICS)
- `spider-snow-sql` / `sf008` (US_REAL_ESTATE)
- `spider-snow-sql` / `sf010` (US_REAL_ESTATE)
- `spider-snow-sql` / `sf011` (CENSUS_GALAXY__ZIP_CODE_TO_BLOCK_GROUP_SAMPLE)
- `spider-snow-sql` / `sf012` (WEATHER__ENVIRONMENT)
- `spider-snow-sql` / `sf014` (CENSUS_GALAXY__AIML_MODEL_DATA_ENRICHMENT_SAMPLE)
- `spider-snow-sql` / `sf018` (BRAZE_USER_EVENT_DEMO_DATASET)
- `spider-snow-sql` / `sf035` (BRAZE_USER_EVENT_DEMO_DATASET)
- `spider-snow-sql` / `sf037` (US_REAL_ESTATE)
- `spider-snow-sql` / `sf040` (US_ADDRESSES__POI)
- `spider-snow-sql` / `sf041` (YES_ENERGY__SAMPLE_DATA)
- `spider-snow-sql` / `sf044` (FINANCE__ECONOMICS)
- `spider-snow-sql` / `sf_bq001` (GA360)
- `spider-snow-sql` / `sf_bq002` (GA360)
- `spider-snow-sql` / `sf_bq003` (GA360)
- `spider-snow-sql` / `sf_bq004` (GA360)
- `spider-snow-sql` / `sf_bq005` (CRYPTO)
- `spider-snow-sql` / `sf_bq007` (CENSUS_BUREAU_ACS_2)
- `spider-snow-sql` / `sf_bq008` (GA360)
- `spider-snow-sql` / `sf_bq009` (GA360)
- `spider-snow-sql` / `sf_bq010` (GA360)
- `spider-snow-sql` / `sf_bq011` (GA4)
- `spider-snow-sql` / `sf_bq012` (ETHEREUM_BLOCKCHAIN)
- `spider-snow-sql` / `sf_bq014` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq015` (STACKOVERFLOW_PLUS)
- `spider-snow-sql` / `sf_bq016` (DEPS_DEV_V1)
- `spider-snow-sql` / `sf_bq017` (GEO_OPENSTREETMAP)
- `spider-snow-sql` / `sf_bq018` (COVID19_OPEN_DATA)
- `spider-snow-sql` / `sf_bq019` (CMS_DATA)
- `spider-snow-sql` / `sf_bq020` (GENOMICS_CANNABIS)
- `spider-snow-sql` / `sf_bq021` (NEW_YORK)
- `spider-snow-sql` / `sf_bq023` (FEC)
- `spider-snow-sql` / `sf_bq024` (USFS_FIA)
- `spider-snow-sql` / `sf_bq025` (CENSUS_BUREAU_INTERNATIONAL)
- `spider-snow-sql` / `sf_bq026` (PATENTS)
- `spider-snow-sql` / `sf_bq027` (PATENTS)
- `spider-snow-sql` / `sf_bq028` (DEPS_DEV_V1)
- `spider-snow-sql` / `sf_bq029` (PATENTS)
- `spider-snow-sql` / `sf_bq030` (COVID19_OPEN_DATA)
- `spider-snow-sql` / `sf_bq031` (NOAA_DATA)
- `spider-snow-sql` / `sf_bq032` (NOAA_DATA)
- `spider-snow-sql` / `sf_bq033` (PATENTS)
- `spider-snow-sql` / `sf_bq034` (GHCN_D)
- `spider-snow-sql` / `sf_bq035` (SAN_FRANCISCO)
- `spider-snow-sql` / `sf_bq036` (GITHUB_REPOS)
- `spider-snow-sql` / `sf_bq037` (HUMAN_GENOME_VARIANTS)
- `spider-snow-sql` / `sf_bq038` (NEW_YORK)
- `spider-snow-sql` / `sf_bq039` (NEW_YORK_PLUS)
- `spider-snow-sql` / `sf_bq040` (NEW_YORK_PLUS)
- `spider-snow-sql` / `sf_bq041` (STACKOVERFLOW)
- `spider-snow-sql` / `sf_bq042` (NOAA_DATA)
- `spider-snow-sql` / `sf_bq043` (TCGA)
- `spider-snow-sql` / `sf_bq044` (TCGA)
- `spider-snow-sql` / `sf_bq045` (NOAA_DATA)
- `spider-snow-sql` / `sf_bq046` (TCGA_BIOCLIN_V0)
- `spider-snow-sql` / `sf_bq047` (NEW_YORK_NOAA)
- `spider-snow-sql` / `sf_bq048` (NEW_YORK_NOAA)
- `spider-snow-sql` / `sf_bq049` (IOWA_LIQUOR_SALES_PLUS)
- `spider-snow-sql` / `sf_bq050` (NEW_YORK_CITIBIKE_1)
- `spider-snow-sql` / `sf_bq051` (NEW_YORK_GHCN)
- `spider-snow-sql` / `sf_bq052` (PATENTSVIEW)
- `spider-snow-sql` / `sf_bq053` (NEW_YORK)
- `spider-snow-sql` / `sf_bq054` (NEW_YORK)
- `spider-snow-sql` / `sf_bq055` (GOOGLE_DEI)
- `spider-snow-sql` / `sf_bq056` (GEO_OPENSTREETMAP_BOUNDARIES)
- `spider-snow-sql` / `sf_bq057` (CRYPTO)
- `spider-snow-sql` / `sf_bq058` (GOOG_BLOCKCHAIN)
- `spider-snow-sql` / `sf_bq059` (SAN_FRANCISCO_PLUS)
- `spider-snow-sql` / `sf_bq060` (CENSUS_BUREAU_INTERNATIONAL)
- `spider-snow-sql` / `sf_bq061` (CENSUS_BUREAU_ACS_1)
- `spider-snow-sql` / `sf_bq062` (DEPS_DEV_V1)
- `spider-snow-sql` / `sf_bq063` (DEPS_DEV_V1)
- `spider-snow-sql` / `sf_bq064` (CENSUS_BUREAU_ACS_1)
- `spider-snow-sql` / `sf_bq065` (CRYPTO)
- `spider-snow-sql` / `sf_bq066` (SDOH)
- `spider-snow-sql` / `sf_bq067` (NHTSA_TRAFFIC_FATALITIES)
- `spider-snow-sql` / `sf_bq068` (CRYPTO)
- `spider-snow-sql` / `sf_bq069` (IDC)
- `spider-snow-sql` / `sf_bq070` (IDC)
- `spider-snow-sql` / `sf_bq071` (NOAA_DATA_PLUS)
- `spider-snow-sql` / `sf_bq072` (DEATH)
- `spider-snow-sql` / `sf_bq073` (CENSUS_BUREAU_ACS_2)
- `spider-snow-sql` / `sf_bq074` (SDOH)
- `spider-snow-sql` / `sf_bq075` (GOOGLE_DEI)
- `spider-snow-sql` / `sf_bq078` (OPEN_TARGETS_PLATFORM_2)
- `spider-snow-sql` / `sf_bq079` (USFS_FIA)
- `spider-snow-sql` / `sf_bq080` (CRYPTO)
- `spider-snow-sql` / `sf_bq081` (SAN_FRANCISCO_PLUS)
- `spider-snow-sql` / `sf_bq083` (CRYPTO)
- `spider-snow-sql` / `sf_bq084` (GOOG_BLOCKCHAIN)
- `spider-snow-sql` / `sf_bq085` (COVID19_JHU_WORLD_BANK)
- `spider-snow-sql` / `sf_bq086` (COVID19_OPEN_WORLD_BANK)
- `spider-snow-sql` / `sf_bq087` (COVID19_SYMPTOM_SEARCH)
- `spider-snow-sql` / `sf_bq088` (COVID19_SYMPTOM_SEARCH)
- `spider-snow-sql` / `sf_bq089` (COVID19_USA)
- `spider-snow-sql` / `sf_bq090` (CYMBAL_INVESTMENTS)
- `spider-snow-sql` / `sf_bq091` (PATENTS)
- `spider-snow-sql` / `sf_bq092` (CRYPTO)
- `spider-snow-sql` / `sf_bq093` (CRYPTO)
- `spider-snow-sql` / `sf_bq094` (FEC)
- `spider-snow-sql` / `sf_bq095` (OPEN_TARGETS_PLATFORM_1)
- `spider-snow-sql` / `sf_bq096` (GBIF)
- `spider-snow-sql` / `sf_bq097` (SDOH)
- `spider-snow-sql` / `sf_bq098` (NEW_YORK_PLUS)
- `spider-snow-sql` / `sf_bq099` (PATENTS)
- `spider-snow-sql` / `sf_bq100` (GITHUB_REPOS)
- `spider-snow-sql` / `sf_bq101` (GITHUB_REPOS)
- `spider-snow-sql` / `sf_bq102` (GNOMAD)
- `spider-snow-sql` / `sf_bq103` (GNOMAD)
- `spider-snow-sql` / `sf_bq104` (GOOGLE_TRENDS)
- `spider-snow-sql` / `sf_bq105` (NHTSA_TRAFFIC_FATALITIES_PLUS)
- `spider-snow-sql` / `sf_bq107` (GENOMICS_CANNABIS)
- `spider-snow-sql` / `sf_bq108` (NHTSA_TRAFFIC_FATALITIES)
- `spider-snow-sql` / `sf_bq109` (OPEN_TARGETS_GENETICS_1)
- `spider-snow-sql` / `sf_bq110` (SDOH)
- `spider-snow-sql` / `sf_bq111` (TCGA_MITELMAN)
- `spider-snow-sql` / `sf_bq112` (BLS)
- `spider-snow-sql` / `sf_bq113` (BLS)
- `spider-snow-sql` / `sf_bq114` (OPENAQ)
- `spider-snow-sql` / `sf_bq115` (CENSUS_BUREAU_INTERNATIONAL)
- `spider-snow-sql` / `sf_bq116` (SEC_QUARTERLY_FINANCIALS)
- `spider-snow-sql` / `sf_bq117` (NOAA_DATA)
- `spider-snow-sql` / `sf_bq118` (DEATH)
- `spider-snow-sql` / `sf_bq119` (NOAA_DATA)
- `spider-snow-sql` / `sf_bq120` (SDOH)
- `spider-snow-sql` / `sf_bq121` (STACKOVERFLOW)
- `spider-snow-sql` / `sf_bq123` (STACKOVERFLOW)
- `spider-snow-sql` / `sf_bq124` (FHIR_SYNTHEA)
- `spider-snow-sql` / `sf_bq126` (THE_MET)
- `spider-snow-sql` / `sf_bq127` (PATENTS_GOOGLE)
- `spider-snow-sql` / `sf_bq128` (PATENTSVIEW)
- `spider-snow-sql` / `sf_bq130` (COVID19_NYT)
- `spider-snow-sql` / `sf_bq131` (GEO_OPENSTREETMAP)
- `spider-snow-sql` / `sf_bq135` (CRYPTO)
- `spider-snow-sql` / `sf_bq136` (CRYPTO)
- `spider-snow-sql` / `sf_bq137` (CENSUS_BUREAU_USA)
- `spider-snow-sql` / `sf_bq141` (TCGA_HG38_DATA_V0)
- `spider-snow-sql` / `sf_bq143` (CPTAC_PDC)
- `spider-snow-sql` / `sf_bq144` (NCAA_INSIGHTS)
- `spider-snow-sql` / `sf_bq147` (TCGA)
- `spider-snow-sql` / `sf_bq148` (TCGA)
- `spider-snow-sql` / `sf_bq150` (TCGA_HG19_DATA_V0)
- `spider-snow-sql` / `sf_bq151` (PANCANCER_ATLAS_2)
- `spider-snow-sql` / `sf_bq152` (TCGA_HG38_DATA_V0)
- `spider-snow-sql` / `sf_bq153` (PANCANCER_ATLAS_1)
- `spider-snow-sql` / `sf_bq154` (PANCANCER_ATLAS_1)
- `spider-snow-sql` / `sf_bq155` (TCGA_HG38_DATA_V0)
- `spider-snow-sql` / `sf_bq156` (PANCANCER_ATLAS_1)
- `spider-snow-sql` / `sf_bq157` (PANCANCER_ATLAS_1)
- `spider-snow-sql` / `sf_bq158` (PANCANCER_ATLAS_1)
- `spider-snow-sql` / `sf_bq159` (PANCANCER_ATLAS_1)
- `spider-snow-sql` / `sf_bq160` (META_KAGGLE)
- `spider-snow-sql` / `sf_bq161` (PANCANCER_ATLAS_2)
- `spider-snow-sql` / `sf_bq162` (HTAN_1)
- `spider-snow-sql` / `sf_bq163` (HTAN_2)
- `spider-snow-sql` / `sf_bq164` (HTAN_2)
- `spider-snow-sql` / `sf_bq165` (MITELMAN)
- `spider-snow-sql` / `sf_bq166` (TCGA_MITELMAN)
- `spider-snow-sql` / `sf_bq167` (META_KAGGLE)
- `spider-snow-sql` / `sf_bq169` (MITELMAN)
- `spider-snow-sql` / `sf_bq171` (META_KAGGLE)
- `spider-snow-sql` / `sf_bq172` (CMS_DATA)
- `spider-snow-sql` / `sf_bq177` (CMS_DATA)
- `spider-snow-sql` / `sf_bq180` (GITHUB_REPOS)
- `spider-snow-sql` / `sf_bq181` (NOAA_DATA)
- `spider-snow-sql` / `sf_bq182` (GITHUB_REPOS_DATE)
- `spider-snow-sql` / `sf_bq184` (CRYPTO)
- `spider-snow-sql` / `sf_bq185` (NEW_YORK_PLUS)
- `spider-snow-sql` / `sf_bq186` (SAN_FRANCISCO)
- `spider-snow-sql` / `sf_bq187` (ETHEREUM_BLOCKCHAIN)
- `spider-snow-sql` / `sf_bq188` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq189` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq190` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq191` (GITHUB_REPOS_DATE)
- `spider-snow-sql` / `sf_bq192` (GITHUB_REPOS_DATE)
- `spider-snow-sql` / `sf_bq193` (GITHUB_REPOS)
- `spider-snow-sql` / `sf_bq194` (GITHUB_REPOS)
- `spider-snow-sql` / `sf_bq195` (CRYPTO)
- `spider-snow-sql` / `sf_bq197` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq198` (NCAA_BASKETBALL)
- `spider-snow-sql` / `sf_bq199` (IOWA_LIQUOR_SALES)
- `spider-snow-sql` / `sf_bq200` (MLB)
- `spider-snow-sql` / `sf_bq202` (NEW_YORK_PLUS)
- `spider-snow-sql` / `sf_bq203` (NEW_YORK_PLUS)
- `spider-snow-sql` / `sf_bq204` (ECLIPSE_MEGAMOVIE)
- `spider-snow-sql` / `sf_bq207` (PATENTS_USPTO)
- `spider-snow-sql` / `sf_bq208` (NEW_YORK_NOAA)
- `spider-snow-sql` / `sf_bq209` (PATENTS)
- `spider-snow-sql` / `sf_bq210` (PATENTS)
- `spider-snow-sql` / `sf_bq211` (PATENTS)
- `spider-snow-sql` / `sf_bq212` (PATENTS)
- `spider-snow-sql` / `sf_bq213` (PATENTS)
- `spider-snow-sql` / `sf_bq214` (PATENTS_GOOGLE)
- `spider-snow-sql` / `sf_bq215` (PATENTS)
- `spider-snow-sql` / `sf_bq216` (PATENTS_GOOGLE)
- `spider-snow-sql` / `sf_bq217` (GITHUB_REPOS_DATE)
- `spider-snow-sql` / `sf_bq218` (IOWA_LIQUOR_SALES)
- `spider-snow-sql` / `sf_bq219` (IOWA_LIQUOR_SALES)
- `spider-snow-sql` / `sf_bq220` (USFS_FIA)
- `spider-snow-sql` / `sf_bq221` (PATENTS)
- `spider-snow-sql` / `sf_bq222` (PATENTS)
- `spider-snow-sql` / `sf_bq223` (PATENTS)
- `spider-snow-sql` / `sf_bq224` (GITHUB_REPOS_DATE)
- `spider-snow-sql` / `sf_bq225` (GITHUB_REPOS)
- `spider-snow-sql` / `sf_bq226` (GOOG_BLOCKCHAIN)
- `spider-snow-sql` / `sf_bq227` (LONDON)
- `spider-snow-sql` / `sf_bq228` (LONDON)
- `spider-snow-sql` / `sf_bq229` (OPEN_IMAGES)
- `spider-snow-sql` / `sf_bq230` (USDA_NASS_AGRICULTURE)
- `spider-snow-sql` / `sf_bq232` (LONDON)
- `spider-snow-sql` / `sf_bq233` (GITHUB_REPOS)
- `spider-snow-sql` / `sf_bq234` (CMS_DATA)
- `spider-snow-sql` / `sf_bq235` (CMS_DATA)
- `spider-snow-sql` / `sf_bq236` (NOAA_DATA_PLUS)
- `spider-snow-sql` / `sf_bq246` (PATENTSVIEW)
- `spider-snow-sql` / `sf_bq247` (PATENTS_GOOGLE)
- `spider-snow-sql` / `sf_bq248` (GITHUB_REPOS)
- `spider-snow-sql` / `sf_bq249` (GITHUB_REPOS)
- `spider-snow-sql` / `sf_bq250` (GEO_OPENSTREETMAP_WORLDPOP)
- `spider-snow-sql` / `sf_bq251` (PYPI)
- `spider-snow-sql` / `sf_bq252` (GITHUB_REPOS)
- `spider-snow-sql` / `sf_bq253` (GEO_OPENSTREETMAP)
- `spider-snow-sql` / `sf_bq254` (GEO_OPENSTREETMAP)
- `spider-snow-sql` / `sf_bq255` (GITHUB_REPOS)
- `spider-snow-sql` / `sf_bq256` (CRYPTO)
- `spider-snow-sql` / `sf_bq258` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq259` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq260` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq261` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq262` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq263` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq264` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq265` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq266` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq268` (GA360)
- `spider-snow-sql` / `sf_bq269` (GA360)
- `spider-snow-sql` / `sf_bq270` (GA360)
- `spider-snow-sql` / `sf_bq271` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq272` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq273` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq275` (GA360)
- `spider-snow-sql` / `sf_bq276` (NOAA_PORTS)
- `spider-snow-sql` / `sf_bq277` (NOAA_PORTS)
- `spider-snow-sql` / `sf_bq278` (SUNROOF_SOLAR)
- `spider-snow-sql` / `sf_bq280` (STACKOVERFLOW)
- `spider-snow-sql` / `sf_bq283` (AUSTIN)
- `spider-snow-sql` / `sf_bq285` (FDA)
- `spider-snow-sql` / `sf_bq287` (FDA)
- `spider-snow-sql` / `sf_bq288` (FDA)
- `spider-snow-sql` / `sf_bq289` (GEO_OPENSTREETMAP_CENSUS_PLACES)
- `spider-snow-sql` / `sf_bq290` (NOAA_DATA)
- `spider-snow-sql` / `sf_bq291` (NOAA_GLOBAL_FORECAST_SYSTEM)
- `spider-snow-sql` / `sf_bq292` (CRYPTO)
- `spider-snow-sql` / `sf_bq293` (NEW_YORK_GEO)
- `spider-snow-sql` / `sf_bq294` (SAN_FRANCISCO_PLUS)
- `spider-snow-sql` / `sf_bq295` (GITHUB_REPOS_DATE)
- `spider-snow-sql` / `sf_bq300` (STACKOVERFLOW)
- `spider-snow-sql` / `sf_bq301` (STACKOVERFLOW)
- `spider-snow-sql` / `sf_bq302` (STACKOVERFLOW)
- `spider-snow-sql` / `sf_bq303` (STACKOVERFLOW)
- `spider-snow-sql` / `sf_bq304` (STACKOVERFLOW)
- `spider-snow-sql` / `sf_bq305` (STACKOVERFLOW)
- `spider-snow-sql` / `sf_bq306` (STACKOVERFLOW)
- `spider-snow-sql` / `sf_bq307` (STACKOVERFLOW)
- `spider-snow-sql` / `sf_bq308` (STACKOVERFLOW)
- `spider-snow-sql` / `sf_bq309` (STACKOVERFLOW)
- `spider-snow-sql` / `sf_bq310` (STACKOVERFLOW)
- `spider-snow-sql` / `sf_bq320` (IDC)
- `spider-snow-sql` / `sf_bq321` (IDC)
- `spider-snow-sql` / `sf_bq323` (IDC)
- `spider-snow-sql` / `sf_bq324` (IDC)
- `spider-snow-sql` / `sf_bq325` (OPEN_TARGETS_GENETICS_2)
- `spider-snow-sql` / `sf_bq326` (WORLD_BANK)
- `spider-snow-sql` / `sf_bq327` (WORLD_BANK)
- `spider-snow-sql` / `sf_bq328` (WORLD_BANK)
- `spider-snow-sql` / `sf_bq330` (FDA)
- `spider-snow-sql` / `sf_bq331` (META_KAGGLE)
- `spider-snow-sql` / `sf_bq333` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq334` (CRYPTO)
- `spider-snow-sql` / `sf_bq335` (CRYPTO)
- `spider-snow-sql` / `sf_bq338` (CENSUS_BUREAU_ACS_1)
- `spider-snow-sql` / `sf_bq339` (SAN_FRANCISCO_PLUS)
- `spider-snow-sql` / `sf_bq340` (CRYPTO)
- `spider-snow-sql` / `sf_bq341` (CRYPTO)
- `spider-snow-sql` / `sf_bq342` (CRYPTO)
- `spider-snow-sql` / `sf_bq345` (IDC)
- `spider-snow-sql` / `sf_bq346` (IDC)
- `spider-snow-sql` / `sf_bq347` (IDC)
- `spider-snow-sql` / `sf_bq348` (GEO_OPENSTREETMAP)
- `spider-snow-sql` / `sf_bq349` (GEO_OPENSTREETMAP)
- `spider-snow-sql` / `sf_bq350` (OPEN_TARGETS_PLATFORM_1)
- `spider-snow-sql` / `sf_bq352` (SDOH)
- `spider-snow-sql` / `sf_bq354` (CMS_DATA)
- `spider-snow-sql` / `sf_bq355` (CMS_DATA)
- `spider-snow-sql` / `sf_bq356` (NOAA_DATA)
- `spider-snow-sql` / `sf_bq357` (NOAA_DATA)
- `spider-snow-sql` / `sf_bq358` (NEW_YORK_CITIBIKE_1)
- `spider-snow-sql` / `sf_bq359` (GITHUB_REPOS)
- `spider-snow-sql` / `sf_bq360` (NPPES)
- `spider-snow-sql` / `sf_bq361` (THELOOK_ECOMMERCE)
- `spider-snow-sql` / `sf_bq366` (THE_MET)
- `spider-snow-sql` / `sf_bq370` (WIDE_WORLD_IMPORTERS)
- `spider-snow-sql` / `sf_bq371` (WIDE_WORLD_IMPORTERS)
- `spider-snow-sql` / `sf_bq372` (WIDE_WORLD_IMPORTERS)
- `spider-snow-sql` / `sf_bq373` (WIDE_WORLD_IMPORTERS)
- `spider-snow-sql` / `sf_bq374` (GA360)
- `spider-snow-sql` / `sf_bq375` (GITHUB_REPOS)
- `spider-snow-sql` / `sf_bq376` (SAN_FRANCISCO_PLUS)
- `spider-snow-sql` / `sf_bq377` (GITHUB_REPOS)
- `spider-snow-sql` / `sf_bq379` (OPEN_TARGETS_PLATFORM_1)
- `spider-snow-sql` / `sf_bq380` (META_KAGGLE)
- `spider-snow-sql` / `sf_bq383` (GHCN_D)
- `spider-snow-sql` / `sf_bq389` (EPA_HISTORICAL_AIR_QUALITY)
- `spider-snow-sql` / `sf_bq390` (IDC)
- `spider-snow-sql` / `sf_bq391` (FHIR_SYNTHEA)
- `spider-snow-sql` / `sf_bq392` (NOAA_GSOD)
- `spider-snow-sql` / `sf_bq393` (HACKER_NEWS)
- `spider-snow-sql` / `sf_bq394` (NOAA_DATA)
- `spider-snow-sql` / `sf_bq395` (SDOH)
- `spider-snow-sql` / `sf_bq396` (NHTSA_TRAFFIC_FATALITIES)
- `spider-snow-sql` / `sf_bq397` (ECOMMERCE)
- `spider-snow-sql` / `sf_bq398` (WORLD_BANK)
- `spider-snow-sql` / `sf_bq399` (WORLD_BANK)
- `spider-snow-sql` / `sf_bq400` (SAN_FRANCISCO_PLUS)
- `spider-snow-sql` / `sf_bq402` (ECOMMERCE)
- `spider-snow-sql` / `sf_bq403` (IRS_990)
- `spider-snow-sql` / `sf_bq406` (GOOGLE_DEI)
- `spider-snow-sql` / `sf_bq407` (COVID19_USA)
- `spider-snow-sql` / `sf_bq410` (CENSUS_BUREAU_ACS_2)
- `spider-snow-sql` / `sf_bq411` (GOOGLE_TRENDS)
- `spider-snow-sql` / `sf_bq412` (GOOGLE_ADS)
- `spider-snow-sql` / `sf_bq413` (DIMENSIONS_AI_COVID19)
- `spider-snow-sql` / `sf_bq414` (THE_MET)
- `spider-snow-sql` / `sf_bq415` (HUMAN_GENOME_VARIANTS)
- `spider-snow-sql` / `sf_bq416` (GOOG_BLOCKCHAIN)
- `spider-snow-sql` / `sf_bq417` (IDC)
- `spider-snow-sql` / `sf_bq418` (TARGETOME_REACTOME)
- `spider-snow-sql` / `sf_bq419` (NOAA_DATA)
- `spider-snow-sql` / `sf_bq420` (PATENTS_USPTO)
- `spider-snow-sql` / `sf_bq421` (IDC)
- `spider-snow-sql` / `sf_bq422` (IDC)
- `spider-snow-sql` / `sf_bq423` (GOOGLE_ADS)
- `spider-snow-sql` / `sf_bq424` (WORLD_BANK)
- `spider-snow-sql` / `sf_bq425` (EBI_CHEMBL)
- `spider-snow-sql` / `sf_bq426` (NEW_YORK_CITIBIKE_1)
- `spider-snow-sql` / `sf_bq427` (NCAA_BASKETBALL)
- `spider-snow-sql` / `sf_bq428` (NCAA_BASKETBALL)
- `spider-snow-sql` / `sf_bq429` (CENSUS_BUREAU_ACS_2)
- `spider-snow-sql` / `sf_bq430` (EBI_CHEMBL)
- `spider-snow-sql` / `sf_bq432` (FDA)
- `spider-snow-sql` / `sf_bq441` (NHTSA_TRAFFIC_FATALITIES)
- `spider-snow-sql` / `sf_bq442` (CYMBAL_INVESTMENTS)
- `spider-snow-sql` / `sf_bq444` (CRYPTO)
- `spider-snow-sql` / `sf_bq445` (GNOMAD)
- `spider-snow-sql` / `sf_bq450` (ETHEREUM_BLOCKCHAIN)
- `spider-snow-sql` / `sf_bq451` (_1000_GENOMES)
- `spider-snow-sql` / `sf_bq452` (_1000_GENOMES)
- `spider-snow-sql` / `sf_bq453` (_1000_GENOMES)
- `spider-snow-sql` / `sf_bq454` (_1000_GENOMES)
- `spider-snow-sql` / `sf_bq455` (IDC)
- `spider-snow-sql` / `sf_bq456` (IDC)
- `spider-snow-sql` / `sf_bq457` (LIBRARIES_IO)
- `spider-snow-sql` / `sf_bq458` (WORD_VECTORS_US)
- `spider-snow-sql` / `sf_bq459` (WORD_VECTORS_US)
- `spider-snow-sql` / `sf_bq460` (WORD_VECTORS_US)
- `spider-snow-sql` / `sf_bq461` (NCAA_BASKETBALL)
- `spider-snow-sql` / `sf_bq462` (NCAA_BASKETBALL)
- `spider-snow-sql` / `sf_ga001` (GA4)
- `spider-snow-sql` / `sf_ga002` (GA4)
- `spider-snow-sql` / `sf_ga003` (FIREBASE)
- `spider-snow-sql` / `sf_ga004` (GA4)
- `spider-snow-sql` / `sf_ga005` (FIREBASE)
- `spider-snow-sql` / `sf_ga006` (GA4)
- `spider-snow-sql` / `sf_ga007` (GA4)
- `spider-snow-sql` / `sf_ga008` (GA4)
- `spider-snow-sql` / `sf_ga009` (GA4)
- `spider-snow-sql` / `sf_ga010` (GA4)
- `spider-snow-sql` / `sf_ga011` (GA4)
- `spider-snow-sql` / `sf_ga012` (GA4)
- `spider-snow-sql` / `sf_ga013` (GA4)
- `spider-snow-sql` / `sf_ga014` (GA4)
- `spider-snow-sql` / `sf_ga017` (GA4)
- `spider-snow-sql` / `sf_ga018` (GA4)
- `spider-snow-sql` / `sf_ga019` (FIREBASE)
- `spider-snow-sql` / `sf_ga020` (FIREBASE)
- `spider-snow-sql` / `sf_ga021` (FIREBASE)
- `spider-snow-sql` / `sf_ga022` (FIREBASE)
- `spider-snow-sql` / `sf_ga025` (FIREBASE)
- `spider-snow-sql` / `sf_ga028` (FIREBASE)
- `spider-snow-sql` / `sf_ga030` (FIREBASE)
- `spider-snow-sql` / `sf_ga031` (GA4)
- `spider-snow-sql` / `sf_ga032` (GA4)
- `spider-snow-sql` / `sf_local002` (E_COMMERCE)
- `spider-snow-sql` / `sf_local003` (E_COMMERCE)
- `spider-snow-sql` / `sf_local004` (E_COMMERCE)
- `spider-snow-sql` / `sf_local009` (AIRLINES)
- `spider-snow-sql` / `sf_local010` (AIRLINES)
- `spider-snow-sql` / `sf_local015` (CALIFORNIA_TRAFFIC_COLLISION)
- `spider-snow-sql` / `sf_local017` (CALIFORNIA_TRAFFIC_COLLISION)
- `spider-snow-sql` / `sf_local018` (CALIFORNIA_TRAFFIC_COLLISION)
- `spider-snow-sql` / `sf_local019` (WWE)
- `spider-snow-sql` / `sf_local020` (IPL)
- `spider-snow-sql` / `sf_local021` (IPL)
- `spider-snow-sql` / `sf_local022` (IPL)
- `spider-snow-sql` / `sf_local023` (IPL)
- `spider-snow-sql` / `sf_local024` (IPL)
- `spider-snow-sql` / `sf_local025` (IPL)
- `spider-snow-sql` / `sf_local026` (IPL)
- `spider-snow-sql` / `sf_local029` (BRAZILIAN_E_COMMERCE)
- `spider-snow-sql` / `sf_local034` (BRAZILIAN_E_COMMERCE)
- `spider-snow-sql` / `sf_local038` (PAGILA)
- `spider-snow-sql` / `sf_local039` (PAGILA)
- `spider-snow-sql` / `sf_local040` (MODERN_DATA)
- `spider-snow-sql` / `sf_local041` (MODERN_DATA)
- `spider-snow-sql` / `sf_local049` (MODERN_DATA)
- `spider-snow-sql` / `sf_local050` (COMPLEX_ORACLE)
- `spider-snow-sql` / `sf_local054` (CHINOOK)
- `spider-snow-sql` / `sf_local055` (CHINOOK)
- `spider-snow-sql` / `sf_local056` (SQLITE_SAKILA)
- `spider-snow-sql` / `sf_local058` (EDUCATION_BUSINESS)
- `spider-snow-sql` / `sf_local059` (EDUCATION_BUSINESS)
- `spider-snow-sql` / `sf_local060` (COMPLEX_ORACLE)
- `spider-snow-sql` / `sf_local061` (COMPLEX_ORACLE)
- `spider-snow-sql` / `sf_local062` (COMPLEX_ORACLE)
- `spider-snow-sql` / `sf_local063` (COMPLEX_ORACLE)
- `spider-snow-sql` / `sf_local064` (BANK_SALES_TRADING)
- `spider-snow-sql` / `sf_local065` (MODERN_DATA)
- `spider-snow-sql` / `sf_local066` (MODERN_DATA)
- `spider-snow-sql` / `sf_local067` (COMPLEX_ORACLE)
- `spider-snow-sql` / `sf_local068` (CITY_LEGISLATION)
- `spider-snow-sql` / `sf_local070` (CITY_LEGISLATION)
- `spider-snow-sql` / `sf_local071` (CITY_LEGISLATION)
- `spider-snow-sql` / `sf_local072` (CITY_LEGISLATION)
- `spider-snow-sql` / `sf_local073` (MODERN_DATA)
- `spider-snow-sql` / `sf_local074` (BANK_SALES_TRADING)
- `spider-snow-sql` / `sf_local075` (BANK_SALES_TRADING)
- `spider-snow-sql` / `sf_local077` (BANK_SALES_TRADING)
- `spider-snow-sql` / `sf_local078` (BANK_SALES_TRADING)
- `spider-snow-sql` / `sf_local081` (NORTHWIND)
- `spider-snow-sql` / `sf_local085` (NORTHWIND)
- `spider-snow-sql` / `sf_local096` (DB_IMDB)
- `spider-snow-sql` / `sf_local097` (DB_IMDB)
- `spider-snow-sql` / `sf_local098` (DB_IMDB)
- `spider-snow-sql` / `sf_local099` (DB_IMDB)
- `spider-snow-sql` / `sf_local100` (DB_IMDB)
- `spider-snow-sql` / `sf_local114` (EDUCATION_BUSINESS)
- `spider-snow-sql` / `sf_local128` (BOWLINGLEAGUE)
- `spider-snow-sql` / `sf_local130` (SCHOOL_SCHEDULING)
- `spider-snow-sql` / `sf_local131` (ENTERTAINMENTAGENCY)
- `spider-snow-sql` / `sf_local132` (ENTERTAINMENTAGENCY)
- `spider-snow-sql` / `sf_local133` (ENTERTAINMENTAGENCY)
- `spider-snow-sql` / `sf_local141` (ADVENTUREWORKS)
- `spider-snow-sql` / `sf_local152` (IMDB_MOVIES)
- `spider-snow-sql` / `sf_local156` (BANK_SALES_TRADING)
- `spider-snow-sql` / `sf_local157` (BANK_SALES_TRADING)
- `spider-snow-sql` / `sf_local163` (EDUCATION_BUSINESS)
- `spider-snow-sql` / `sf_local167` (CITY_LEGISLATION)
- `spider-snow-sql` / `sf_local168` (CITY_LEGISLATION)
- `spider-snow-sql` / `sf_local169` (CITY_LEGISLATION)
- `spider-snow-sql` / `sf_local170` (CITY_LEGISLATION)
- `spider-snow-sql` / `sf_local171` (CITY_LEGISLATION)
- `spider-snow-sql` / `sf_local193` (SQLITE_SAKILA)
- `spider-snow-sql` / `sf_local194` (SQLITE_SAKILA)
- `spider-snow-sql` / `sf_local195` (SQLITE_SAKILA)
- `spider-snow-sql` / `sf_local196` (SQLITE_SAKILA)
- `spider-snow-sql` / `sf_local197` (SQLITE_SAKILA)
- `spider-snow-sql` / `sf_local198` (CHINOOK)
- `spider-snow-sql` / `sf_local199` (SQLITE_SAKILA)
- `spider-snow-sql` / `sf_local201` (MODERN_DATA)
- `spider-snow-sql` / `sf_local202` (CITY_LEGISLATION)
- `spider-snow-sql` / `sf_local209` (DELIVERY_CENTER)
- `spider-snow-sql` / `sf_local210` (DELIVERY_CENTER)
- `spider-snow-sql` / `sf_local212` (DELIVERY_CENTER)
- `spider-snow-sql` / `sf_local218` (EU_SOCCER)
- `spider-snow-sql` / `sf_local219` (EU_SOCCER)
- `spider-snow-sql` / `sf_local220` (EU_SOCCER)
- `spider-snow-sql` / `sf_local221` (EU_SOCCER)
- `spider-snow-sql` / `sf_local228` (IPL)
- `spider-snow-sql` / `sf_local229` (IPL)
- `spider-snow-sql` / `sf_local230` (IMDB_MOVIES)
- `spider-snow-sql` / `sf_local244` (MUSIC)
- `spider-snow-sql` / `sf_local253` (EDUCATION_BUSINESS)
- `spider-snow-sql` / `sf_local258` (IPL)
- `spider-snow-sql` / `sf_local259` (IPL)
- `spider-snow-sql` / `sf_local262` (STACKING)
- `spider-snow-sql` / `sf_local263` (STACKING)
- `spider-snow-sql` / `sf_local264` (STACKING)
- `spider-snow-sql` / `sf_local269` (ORACLE_SQL)
- `spider-snow-sql` / `sf_local270` (ORACLE_SQL)
- `spider-snow-sql` / `sf_local272` (ORACLE_SQL)
- `spider-snow-sql` / `sf_local273` (ORACLE_SQL)
- `spider-snow-sql` / `sf_local274` (ORACLE_SQL)
- `spider-snow-sql` / `sf_local275` (ORACLE_SQL)
- `spider-snow-sql` / `sf_local277` (ORACLE_SQL)
- `spider-snow-sql` / `sf_local279` (ORACLE_SQL)
- `spider-snow-sql` / `sf_local283` (EU_SOCCER)
- `spider-snow-sql` / `sf_local284` (BANK_SALES_TRADING)
- `spider-snow-sql` / `sf_local285` (BANK_SALES_TRADING)
- `spider-snow-sql` / `sf_local286` (ELECTRONIC_SALES)
- `spider-snow-sql` / `sf_local297` (BANK_SALES_TRADING)
- `spider-snow-sql` / `sf_local298` (BANK_SALES_TRADING)
- `spider-snow-sql` / `sf_local299` (BANK_SALES_TRADING)
- `spider-snow-sql` / `sf_local300` (BANK_SALES_TRADING)
- `spider-snow-sql` / `sf_local301` (BANK_SALES_TRADING)
- `spider-snow-sql` / `sf_local302` (BANK_SALES_TRADING)
- `spider-snow-sql` / `sf_local309` (F1)
- `spider-snow-sql` / `sf_local310` (F1)
- `spider-snow-sql` / `sf_local311` (F1)
- `spider-snow-sql` / `sf_local329` (LOG)
- `spider-snow-sql` / `sf_local330` (LOG)
- `spider-snow-sql` / `sf_local331` (LOG)
- `spider-snow-sql` / `sf_local335` (F1)
- `spider-snow-sql` / `sf_local336` (F1)
- `spider-snow-sql` / `sf_local344` (F1)
- `spider-snow-sql` / `sf_local354` (F1)
- `spider-snow-sql` / `sf_local355` (F1)
- `spider-snow-sql` / `sf_local356` (F1)
- `spider-snow-sql` / `sf_local358` (LOG)
- `spider-snow-sql` / `sf_local360` (LOG)

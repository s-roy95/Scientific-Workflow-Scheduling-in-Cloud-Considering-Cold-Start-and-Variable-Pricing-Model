# Scientific Workflow Scheduling in Cloud Considering Cold Start and Variable Pricing Model

## Dataset

The `Dataset` folder contains the following components:

- `Parsed/`: **Parsed Pegasus Workflow Benchmark files** in `.txt` format.
- `spotprices.csv`: **Spot price history** for cloud instances.
- `pricing.csv`: **On-demand and reserved VM pricing data**.
- `Spot_Pred.csv`: **Predicted spot prices** for proactive scheduling strategies.

---

## Code

The `Code` folder includes the core implementation of all scientific workflow scheduling approaches, as well as helper modules and utility scripts.

### Implemented Approaches

| Script                   | Description                                                                                       |
| ------------------------ | ------------------------------------------------------------------------------------------------- |
| `D_DCD.py`               | Implements the **DCD approach** using **only on-demand instances**.                               |
| `D_Random.py`            | Implements a **random baseline approach** using only on-demand instances.                         |
| `D_SOTA.py`              | Implements the **FaasCache approach**, a state-of-the-art method using only on-demand instances.  |
| `DS_SOTA2.py`            | Implements the **CEWB approach** using both on-demand and spot instances.                         |
| `RDS_DCD.py`             | Implements the **DCD approach** using reserved, on-demand, and spot instances.                    |
| `RDS_DCD_Prediction.py`  | Implements a **prediction-augmented DCD approach** using reserved, on-demand, and spot instances. |
| `RDS_Random.py`          | Implements a **random baseline approach** using reserved, on-demand, and spot instances.          |
| `RD_DCD.py`              | Implements the **DCD approach** using reserved and on-demand instances.                           |
| `helper_classes.py`      | Contains utility classes and helper functions used across all approaches.                         |
| `workflows_and_tasks.py` | Parses workflow benchmark files and builds internal workflow/task structures.                     |
| `main.py`                | Entry point script for executing simulations and comparing different scheduling strategies.       |

---

## Project Directory Structure

```text
.
├── Code
│   ├── D_DCD.py
│   ├── D_Random.py
│   ├── D_SOTA.py
│   ├── DS_SOTA2.py
│   ├── RDS_DCD.py
│   ├── RDS_DCD_Prediction.py
│   ├── RDS_Random.py
│   ├── RD_DCD.py
│   ├── helper_classes.py
│   ├── workflows_and_tasks.py
│   └── main.py
├── Dataset
│   ├── pricing.csv
│   ├── spotprices.csv
│   ├── Spot_Pred.csv
│   └── Parsed/
│       ├── CyberShake_*.txt
│       ├── Epigenomics_*.txt
│       ├── Inspiral_*.txt
│       ├── Montage_*.txt
│       ├── Sipht_*.txt
│       ├── avianflu_*.txt
│       ├── motif_*.txt
│       ├── psload_*.txt
│       ├── psmerge_*.txt
│       ├── scoop_*.txt
│       ├── floodplain.txt
│       ├── gene2life.txt
│       ├── glimmer.txt
│       ├── leaddas.txt
│       ├── leaddm.txt
│       ├── leadmm.txt
│       ├── mcstas.txt
│       ├── mememast.txt
│       └── molsci.txt
```

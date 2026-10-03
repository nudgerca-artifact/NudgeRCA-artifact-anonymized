"""Central paths and settings of the masking runs (paths relative to the folder above common/).
The runs read the Section 3 Bank case files (preprocess-v4/) and write results/ and structures/ beside them."""
import os

REPO       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREPROCESS = os.path.join(REPO, "preprocess-v4")
SPLIT      = os.path.join(PREPROCESS, "_split60-40")
RESULTS    = os.path.join(REPO, "results")
STRUCTS    = os.path.join(REPO, "structures")

DATASETS = {
    "OpenRCA/Bank":       {"dir": f"{PREPROCESS}/OpenRCA/output/Bank",       "out": "OpenRCA_Bank",       "level": "component"},
    "OpenRCA/Telecom":    {"dir": f"{PREPROCESS}/OpenRCA/output/Telecom",    "out": "OpenRCA_Telecom",    "level": "component"},
    "Nezha/TrainTicket":  {"dir": f"{PREPROCESS}/Nezha/output/TrainTicket",  "out": "Nezha_TrainTicket",  "level": "component"},
    "Nezha/HipsterShop":  {"dir": f"{PREPROCESS}/Nezha/output/HipsterShop",  "out": "Nezha_HipsterShop",  "level": "component"},
    "Eadro/TrainTicket":  {"dir": f"{PREPROCESS}/Eadro/output/TT",           "out": "Eadro_TT",           "level": "component"},
    "Eadro/SN":           {"dir": f"{PREPROCESS}/Eadro/output/SN",           "out": "Eadro_SN",           "level": "component"},
    "DejaVu/Oracle":      {"dir": f"{PREPROCESS}/DejaVu/output/Oracle",      "out": "DejaVu_Oracle",      "level": "metric"},
    "DejaVu/TrainTicket": {"dir": f"{PREPROCESS}/DejaVu/output/TrainTicket", "out": "DejaVu_TrainTicket", "level": "component"},
    "AIOps2025":          {"dir": f"{PREPROCESS}/AIOps2025/output",          "out": "AIOps2025",          "level": "component"},
}

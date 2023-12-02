import numpy as np


from sklearn.metrics import (
    confusion_matrix,
    roc_curve,
    precision_score,
    recall_score,
    f1_score,
    mean_absolute_error,
    mean_absolute_percentage_error,
)
from torch.utils.data import DataLoader

import seisbench.generate as sbg
from seisbench.data import WaveformDataset
from seisbench.util import worker_seeding

from augmentations import ChangeChannels
from utils import predict

phase_dict = {
    "trace_p_arrival_sample": "P",
    "trace_pP_arrival_sample": "P",
    "trace_P_arrival_sample": "P",
    "trace_P1_arrival_sample": "P",
    "trace_Pg_arrival_sample": "P",
    "trace_Pn_arrival_sample": "P",
    "trace_PmP_arrival_sample": "P",
    "trace_pwP_arrival_sample": "P",
    "trace_pwPm_arrival_sample": "P",
    "trace_s_arrival_sample": "S",
    "trace_S_arrival_sample": "S",
    "trace_S1_arrival_sample": "S",
    "trace_Sg_arrival_sample": "S",
    "trace_SmS_arrival_sample": "S",
    "trace_Sn_arrival_sample": "S",
}


def get_eval_augmentations():
    p_phases = [key for key, val in phase_dict.items() if val == "P"]
    s_phases = [key for key, val in phase_dict.items() if val == "S"]

    detection_labeller = sbg.DetectionLabeller(
        p_phases, s_phases=s_phases, key=("X", "detections")
    )

    return [
        # sbg.SteeredWindow(windowlen=6000, strategy="pad"),
        sbg.ProbabilisticLabeller(label_columns=phase_dict, sigma=20, dim=0),
        detection_labeller,
        sbg.ChangeDtype(np.float32, "X"),
        sbg.ChangeDtype(np.float32, "y"),
        sbg.ChangeDtype(np.float32, "detections"),
        ChangeChannels(0),
        sbg.Normalize(detrend_axis=-1, amp_norm_axis=-1, amp_norm_type="peak"),
    ]


def eval(
    model,
    data: WaveformDataset,
    batch_size=100,
    num_workers=0,
    detection_threshold: float = 0.5,
):
    """Evaluate model on data and return a bunch of resulting metrics.

    Keys in result:
    - det_precision_score
    -"""
    print("Enter eval.")
    print("Load data.")
    data_generator = sbg.GenericGenerator(data)
    data_generator.add_augmentations(get_eval_augmentations())
    data_loader = DataLoader(
        data_generator,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        worker_init_fn=worker_seeding,
    )

    det_true = []
    p_true = []
    s_true = []

    print("Build ground truth.")
    for idx in range(len(data)):
        _, metadata = data.get_sample(idx)
        det = metadata["trace_category"] == "earthquake_local"
        p = metadata["trace_p_arrival_sample"]
        s = metadata["trace_s_arrival_sample"]

        det_true.append(det)
        p_true.append(p)
        s_true.append(s)

    p_true = np.array(p_true)
    s_true = np.array(s_true)

    print("Run predictions.")
    predictions = predict(model, data_loader)["predictions"]
    det_pred = predictions[:, 0]
    p_pred = predictions[:, 1]
    s_pred = predictions[:, 2]

    # Remove predictions that come from noise.
    nans = p_true[p_true.isnan]
    p_true = p_true[~nans]
    s_true = s_true[~nans]
    p_pred = p_pred[~nans]
    s_pred = s_pred[~nans]

    print("Evaluate predictions.")
    det_roc = roc_curve(det_true, det_pred)

    # NOTE: detection_threshold is a hyperparamater
    det_pred = np.ceil(det_pred - detection_threshold)

    results = dict()

    results["det_roc"] = det_roc
    for det_metric in [confusion_matrix, precision_score, recall_score, f1_score]:
        results[f"det_{det_metric.__name__}"] = det_metric(det_true, det_pred)

    for pick, true, pred in [("p", p_true, p_pred), ("s", s_true, s_pred)]:
        # TODO Mousavi, et. al also report Precision, Recall, and F1 for the regression, which I do not know how to interpret.
        for name, metric in [("mu", np.mean), ("std", np.std)]:
            results[f"{pick}_{name}"] = metric(true - pred)
        for name, metric in [
            ("MAE", mean_absolute_error),
            ("MAPE", mean_absolute_percentage_error),
        ]:
            results[f"{pick}_{name}"] = metric(true, pred)

    return results

"""Answer-matching rules per dataset (task) type, selected by the level field of the config.

component : component (instance name) ranking. The prediction is contained in the GT (pred⊆gt).
            e.g. GT 'ts-preserve-service-b5ccf8557-j4txs', pred 'ts-preserve-service'
metric    : root-cause KPI ranking. The GT can be a compound 'A;B', and the model's prediction is
            a decorated KPI name that *contains* the GT (e.g. GT 'log file sync',
            pred 'log_file_sync平均等待时间'), so we split and match in both directions.

Default = strict (digits kept): the earlier gt-guided matcher also removed digits, so MG01↔MG02
matched and scores were inflated (Bank top1 0.395→0.160). The substring rule is kept, so pod
hashes are still absorbed. loose is also provided for comparison with earlier experiment numbers.
Confusing sibling instances (MG01↔MG02) is itself a pitfall candidate and must count as a failure.
"""
import re

PAT_LOOSE  = r'[^一-龥a-zA-Z]'      # removes digits (earlier gt-guided scheme)
PAT_STRICT = r'[^一-龥a-zA-Z0-9]'   # keeps digits


def _norm(x, pat=PAT_STRICT):
    return re.sub(pat, '', str(x)).lower()


def _mk_component(pat):
    def match(pred, gt):
        p, g = _norm(pred, pat), _norm(gt, pat)
        return bool(p and g) and (p in g)
    return match


def _mk_metric(pat):
    def match(pred, gt):
        p = _norm(pred, pat)
        if not p:
            return False
        for seg in re.split(r'[;；]', str(gt)):
            g = _norm(seg, pat)
            if g and (p in g or g in p):
                return True
        return False
    return match


match_component = _mk_component(PAT_STRICT)
match_metric = _mk_metric(PAT_STRICT)
MATCHERS = {"component": match_component, "metric": match_metric}
MATCHERS_LOOSE = {"component": _mk_component(PAT_LOOSE), "metric": _mk_metric(PAT_LOOSE)}


def get_matcher(level, loose=False):
    """level → matching function (strict by default). loose=True is for comparison with earlier experiments."""
    table = MATCHERS_LOOSE if loose else MATCHERS
    return table.get(level, table["component"])


def gt_rank(preds, gt, level, loose=False):
    """Rank of the GT in rank_list (1-based, None if absent). If the GT is a list (multiple answers), any match counts."""
    if not gt:
        return None
    gts = gt if isinstance(gt, list) else [gt]
    match = get_matcher(level, loose=loose)
    for i, p in enumerate(preds or [], 1):
        if any(match(p, g) for g in gts):
            return i
    return None

"""Write notebooks/results.ipynb (outputs cleared). Run from anywhere: python scripts/build_notebook.py"""

from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

CELLS = [
    ("md", "# Results\n\nSet `RUN_ID`, then run all cells. Reads `results/<RUN_ID>/*.csv`, `runs/<RUN_ID>/clips.csv` "
           "and `runs/<RUN_ID>/raw/*.json`. The charts only show what the CSVs hold: a pilot with 2 speakers per "
           "region is a pipeline check, not a regional finding."),
    # 1. load
    ("code", '''RUN_ID = "demo-004"

import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import HTML, Audio, display

if Path.cwd().name == "notebooks":  # every path in the CSVs is relative to the repo root
    os.chdir("..")
results = Path("results") / RUN_ID
run = Path("runs") / RUN_ID

utterances = pd.read_csv(results / "utterance_scores.csv")
speakers = pd.read_csv(results / "speaker_scores.csv")
summary = pd.read_csv(results / "region_summary.csv")
pairs = pd.read_csv(results / "error_pairs.csv", keep_default_na=False)
clips = pd.read_csv(run / "clips.csv", keep_default_na=False)
tasks = sorted(summary["task"].unique())  # empty for a run with no scored pilot clips (e.g. the demo set)
print(RUN_ID, "-", len(clips), "clips;", utterances["status"].value_counts().to_dict())
# region_summary is empty for a demo-only run (no region/task); per-clip WER is in utterances instead.
display(utterances[["clip_id", "status", "n_ref", "n_hyp", "subs", "dels", "ins", "wer"]])
summary'''),
    # 2. WER by region
    ("code", '''# WER by region, one panel per task. Hatched bars: low_n. Error bars: 95% bootstrap CI (only with 5+ speakers).
fig, axes = plt.subplots(1, max(len(tasks), 1), figsize=(6 * max(len(tasks), 1), 4), squeeze=False)
for ax, task in zip(axes[0], tasks):
    d = summary[summary["task"] == task]
    err = [d["wer"] - d["ci_lo"], d["ci_hi"] - d["wer"]]  # NaN (no bar) where there is no CI
    bars = ax.bar(d["region"], d["wer"], yerr=err, capsize=4, color="tab:blue")
    for bar, low in zip(bars, d["low_n"]):
        if low:
            bar.set_hatch("//")
    ax.set_title(f"{task} (hatched = fewer than 5 speakers)")
    ax.set_ylabel("WER")
plt.show()'''),
    # 3. S/D/I
    ("code", '''# Substitution, deletion and insertion rates (errors per reference word) by region
fig, axes = plt.subplots(1, max(len(tasks), 1), figsize=(6 * max(len(tasks), 1), 4), squeeze=False)
for ax, task in zip(axes[0], tasks):
    d = summary[summary["task"] == task].set_index("region")
    rates = pd.DataFrame({"subs": d["subs"] / d["n_ref"], "dels": d["dels"] / d["n_ref"], "ins": d["ins"] / d["n_ref"]})
    rates.plot.bar(stacked=True, ax=ax, title=task, ylabel="errors per reference word", rot=0)
plt.show()'''),
    # 4. strip plot
    ("code", '''# One dot per speaker: WER by region
fig, axes = plt.subplots(1, max(len(tasks), 1), figsize=(6 * max(len(tasks), 1), 4), squeeze=False)
for ax, task in zip(axes[0], tasks):
    d = speakers[speakers["task"] == task]
    regions = list(summary[summary["task"] == task]["region"])
    for x, region in enumerate(regions):
        w = d[d["region"] == region]["wer"]
        ax.scatter([x + (i - (len(w) - 1) / 2) * 0.06 for i in range(len(w))], w, color="tab:blue", alpha=0.7)
    ax.set_xticks(range(len(regions)), regions)
    ax.set_title(task)
    ax.set_ylabel("speaker WER")
plt.show()'''),
    # 5. error pairs
    ("code", '''# The five most frequent errors per region (ref_word empty = insertion, hyp_word empty = deletion)
pairs.groupby(["task", "region"]).head(5).reset_index(drop=True)'''),
    # 6. clip browser
    ("code", '''# Clip browser: audio, reference and hypothesis side by side; differing words are highlighted.
# The words shown are normalised (lower case, no punctuation), as they are scored, not the original text.
from ukstt.normalise import normalise_default
from ukstt.score import align

MARK = "<b style='background:#ffd54f'>{}</b>"
for clip in clips.to_dict("records"):
    print()
    print(clip["clip_id"], "|", clip["set"], "|", clip["region"], "|", clip["speaker_id"])
    if Path(clip["audio_path"]).exists():
        display(Audio(filename=clip["audio_path"]))
    else:
        print("(audio file not found:", clip["audio_path"] + ")")
    raw = run / "raw" / (clip["clip_id"] + ".json")
    hyp = normalise_default(json.loads(raw.read_text(encoding="utf-8"))["text"]) if raw.exists() else None
    ref = normalise_default(Path(clip["reference_path"]).read_text(encoding="utf-8")) if clip["reference_path"] else None
    if hyp is None:
        display(HTML("<i>no transcript (failed or not run)</i>"))
    elif ref is None:
        display(HTML("<b>hypothesis:</b> " + " ".join(hyp) + " <i>(no reference)</i>"))
    else:
        left, right = [], []
        for kind, r, h in align(ref, hyp).ops:
            left.append(r if kind == "H" else MARK.format(r) if r else "")
            right.append(h if kind == "H" else MARK.format(h) if h else "")
        display(HTML("<table><tr><th>reference</th><th>hypothesis</th></tr><tr>"
                     f"<td style='vertical-align:top'>{' '.join(w for w in left if w)}</td>"
                     f"<td style='vertical-align:top'>{' '.join(w for w in right if w)}</td></tr></table>"))'''),
]


def build() -> nbformat.NotebookNode:
    nb = new_notebook(metadata={"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}})
    for i, (kind, source) in enumerate(CELLS):
        make = new_markdown_cell if kind == "md" else new_code_cell
        nb.cells.append(make(source, id=f"cell-{i}"))
    return nb


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "notebooks" / "results.ipynb"
    out.parent.mkdir(exist_ok=True)
    nbformat.write(build(), out)
    print(f"wrote {out}")

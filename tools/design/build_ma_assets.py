"""Build editable technical figures and previews of received numeric observations.

Run from repository root with python -m tools.design.build_ma_assets.
Requires NumPy and Pillow for optional observation contact sheets.
"""
import argparse
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def text(x, y, value, size=22, weight="normal", color="#20344b", anchor="start"):
    return '<text x="%s" y="%s" font-size="%s" font-weight="%s" fill="%s" text-anchor="%s">%s</text>' % (
        x, y, size, weight, color, anchor, escape(value))


def multiline(x, y, lines, size=22, leading=29, **kwargs):
    return "\n".join(text(x, y + i * leading, line, size, **kwargs) for i, line in enumerate(lines))


def document(elements):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" '
            'markerHeight="8" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="#31628a"/></marker></defs>'
            '<rect width="1280" height="720" fill="white"/>'
            '<g font-family="Times New Roman,serif">' + "\n".join(elements) + '</g></svg>\n')


def recovery_figure():
    items = [text(48, 60, "Recovery proposals and execution authority", 37, "bold"),
             text(48, 104, "The task coordinator authorizes each accepted segment", 24),
             text(48, 148, "Choice: centralized checks. Cost: additional protocol and dispatch latency.", 21)]
    boxes = [
        (48, 232, "Observations", ["RGB and robot state", "Past frames and masks", "Goal and budget"]),
        (352, 232, "Recovery worker", ["Detect supported errors", "Generate and score", "Return proposals only"]),
        (672, 256, "Task coordinator", ["Authority and generation", "Freshness and action limits", "Budget and calibration", "Persist before dispatch"]),
        (1000, 232, "Simulation adapter", ["Accept current commands", "Execute finite segment", "Measured feedback", "Fence revoked generations"]),
    ]
    for x, width, title, body in boxes:
        items += ['<rect x="%s" y="200" width="%s" height="190" rx="8" fill="#eef4f8" stroke="#31628a" stroke-width="2"/>' % (x, width),
                  text(x + width / 2, 238, title, 23, "bold", anchor="middle"),
                  multiline(x + 16, 278, body, 19, 28)]
    for start, end, label in ((280, 352, "context"), (584, 672, "propose"), (928, 1000, "dispatch")):
        items += ['<path d="M %s 295 H %s" fill="none" stroke="#31628a" stroke-width="2.2" marker-end="url(#arrow)"/>' % (start, end - 4),
                  text((start + end) / 2, 275, label, 17, anchor="middle")]
    items += ['<path d="M800 390 V464" fill="none" stroke="#31628a" stroke-width="2.2" marker-end="url(#arrow)"/>',
              text(814, 435, "reject", 19),
              '<rect x="672" y="468" width="256" height="66" rx="8" fill="#fff4df" stroke="#b88322" stroke-width="2"/>',
              text(800, 508, "Reobserve / stop / help", 23, anchor="middle"),
              '<path d="M1116 390 V600 H164 V394" fill="none" stroke="#31628a" stroke-width="2.2" marker-end="url(#arrow)"/>',
              text(640, 581, "Measured feedback and a new observation", 23, anchor="middle"),
              text(48, 675, "Design baseline. Stop confirmation requires fresh measurements and an active generation barrier.", 20)]
    return document(items)


def risk_figure():
    items = [text(48, 60, "Open issues and verification", 37, "bold"),
             text(48, 105, "Current evidence covers 153 normal frames. Recovery experiments remain pending.", 24),
             '<rect x="48" y="150" width="1184" height="48" fill="#203f60"/>']
    for x, label in ((64, "Open issue"), (306, "Part III verification"), (848, "Fallback")):
        items.append(text(x, 182, label, 23, "bold", "white"))
    rows = [
        (["Input semantics"], "Zhang + Ma", ["Capture runtime joint maps, units, clocks", "and actual command feedback."],
         ["Reject unsupported online profiles.", "Keep old data for offline work."]),
        (["Cancellation and stop"], "Zhang + Ma", ["Delay an old command until after halt.", "Verify fencing and measured rest."],
         ["Keep the stop lock until evidence", "passes the SRS conditions."]),
        (["Recovery value"], "Ma + Hu", ["Collect comparable recovery branches.", "Test H1 / H2, baselines and calibration."],
         ["Use offline ranking while evidence", "or probability calibration is missing."]),
    ]
    for index, (label, owner, checks, fallback) in enumerate(rows):
        y = 198 + 132 * index
        items += ['<rect x="48" y="%s" width="1184" height="132" fill="%s"/>' % (y, "#f0f4f8" if index % 2 == 0 else "#ffffff"),
                  multiline(64, y + 43, label, 23), text(64, y + 94, owner, 20, color="#526b83"),
                  multiline(306, y + 43, checks, 23, 32), multiline(848, y + 43, fallback, 22, 32)]
    items += [text(48, 642, "Each PoC records raw evidence, pass/fail criteria, a responsible member and the fallback.", 22),
              text(48, 682, "Status: design plan. Recovery performance and physical stopping await validation.", 20)]
    return document(items)


def contact_sheet(directory, label, output):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from research_tools.legacy_observations import load_export
    rows = load_export(directory)
    font_path = Path("C:/Windows/Fonts/times.ttf")
    if not font_path.exists():
        raise FileNotFoundError("Times New Roman required; provide the font on this platform")
    title_font, body_font = ImageFont.truetype(str(font_path), 29), ImageFont.truetype(str(font_path), 20)
    sheet = Image.new("RGB", (1040, 980), "white")
    draw = ImageDraw.Draw(sheet)
    draw.text((20, 14), "Received normal demonstration: " + label, fill="#20344b", font=title_font)
    draw.text((20, 54), "Stage labels from the export. Record indices do not establish physical time.", fill="#526b83", font=body_font)
    selected = []
    for stage_no, stage in enumerate(("stage_1", "stage_2", "stage_3")):
        part = [r for r in rows if r["stage"] == stage]
        for column, index in enumerate((0, len(part) // 2, len(part) - 1)):
            row = part[index]
            image = Image.fromarray(np.load(Path(directory) / row["rgb"]["path"], allow_pickle=False))
            image = image.resize((320, 240), resample=Image.Resampling.LANCZOS)
            x, y = 20 + column * 340, 104 + stage_no * 278
            sheet.paste(image, (x, y))
            draw.text((x, y + 244), "%s / record %d" % (stage, row["index"]), fill="#20344b", font=body_font)
            selected.append({"frame_id": row["frame_id"], "source_rgb": row["rgb"]["path"], "source_sha256": row["rgb"]["sha256"]})
    draw.text((20, 940), "Normal observations only. No recovery outcome or quality label is inferred.", fill="#526b83", font=body_font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    return {"label": label, "figure": output.relative_to(ROOT).as_posix(), "selected_records": selected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data2")
    parser.add_argument("--data3")
    args = parser.parse_args()
    design = ROOT / "docs/design/figures"
    design.mkdir(parents=True, exist_ok=True)
    for name, svg in (("ma-recovery-authority.svg", recovery_figure()), ("ma-open-issues.svg", risk_figure())):
        (design / name).write_text(svg, encoding="utf-8")
    previews = []
    for label, directory in (("data2", args.data2), ("data3", args.data3)):
        if directory:
            previews.append(contact_sheet(directory, label, ROOT / "docs/research/figures" / (label + "-observation-preview.png")))
    if previews:
        (ROOT / "docs/research/figures/preview-index.json").write_text(
            json.dumps({"purpose": "normal_observation_preview", "figures": previews}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built editable SVG figures and %d observation previews" % len(previews))


if __name__ == "__main__":
    main()

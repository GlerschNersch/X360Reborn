"""Print a compact element tree of a XUI v12 XML file (class, Id, size, position, extras).

Usage: python -I xuitree.py <file.xui> [--timelines]
"""
import sys
import xml.etree.ElementTree as ET

SHOW = ("Width", "Height", "Position", "Opacity", "Visual", "ImagePath", "Text", "ClassOverride",
        "Anchor", "Show", "Pivot", "Scale", "TextColor", "PointSize", "Font", "Fill")


def props(el):
    p = el.find("Properties")
    if p is None:
        return {}
    return {c.tag: (c.text or "").strip() if len(c) == 0 else "<obj>" for c in p}


def fmt_vec(v):
    return ",".join(f"{float(x):g}" for x in v.split(","))


def walk(el, depth, timelines):
    for c in el:
        if c.tag in ("Properties",):
            continue
        if c.tag == "Timelines":
            if timelines:
                dump_timelines(c, depth)
            continue
        p = props(c)
        bits = []
        for k in SHOW:
            if k in p and k not in ("Width", "Height"):
                v = p[k]
                if k in ("Position", "Pivot", "Scale"):
                    v = fmt_vec(v)
                bits.append(f"{k}={v}")
        size = f"{float(p.get('Width', 60)):g}x{float(p.get('Height', 30)):g}"
        print(f"{'  ' * depth}{c.tag} [{p.get('Id', '')}] {size} " + " ".join(bits))
        walk(c, depth + 1, timelines)


def dump_timelines(tl, depth):
    pad = "  " * depth
    for nf in tl.iter("NamedFrame"):
        print(f"{pad}@frame {nf.findtext('Time')} {nf.findtext('Name')} {nf.findtext('Command') or ''}")
    for t in tl.iter("Timeline"):
        target = t.findtext("Id")
        props_ = [p.text for p in t.findall("TimelineProp")]
        for kf in t.findall("KeyFrame"):
            vals = [v.text for v in kf.findall("Prop")]
            print(f"{pad}  ~{target} t={kf.findtext('Time')} interp={kf.findtext('Interpolation')} "
                  + " ".join(f"{n}={v}" for n, v in zip(props_, vals)))


def main():
    root = ET.parse(sys.argv[1]).getroot()
    walk(root, 0, "--timelines" in sys.argv)


if __name__ == "__main__":
    main()

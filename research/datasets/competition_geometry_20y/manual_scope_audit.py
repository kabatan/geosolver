#!/usr/bin/env python3
"""Apply the human, statement-by-statement scope audit.

The extraction files are only candidate inventories.  This file is the
reviewer's ledger: every extracted AIME/HMMT row is assigned a decision after
reading its statement, and the 20 JMO official scans are represented by the
individual problem numbers that were read from the scans.  No geometric
quantity is derived here; the source statement remains the authority.

The HMMT 2011 Alg/Calc/Comb files repeat the same five statements.  They are
kept as source rows but receive a common ``dedupe_key`` so that the reported
scope total is both reproducible and not inflated by those repeated PDFs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


# These are the numbers checked against the full AIME statements.  The 2025
# API rows use IDs such as ``2025-I-2`` (without the AIME prefix), hence the
# helper below normalises both spellings.
AIME_IN_SCOPE: dict[int, set[str]] = {
    2006: {"I-01", "I-07", "II-01", "II-06", "II-09", "II-12"},
    2007: {"I-09", "I-12", "I-15", "II-09", "II-15"},
    2008: {"I-02", "I-10", "II-05", "II-11"},
    2009: {"I-05", "I-12", "II-05", "II-10"},
    2010: {"I-13", "I-15", "II-09", "II-14", "II-15"},
    2011: {"I-02", "I-03", "I-04", "I-14", "II-02", "II-04", "II-10", "II-13"},
    2012: {"I-12", "II-13", "II-15"},
    2013: {"I-03", "I-09", "I-12", "II-04", "II-05", "II-08", "II-13", "II-15"},
    2014: {"I-13", "I-15", "II-03", "II-08", "II-11", "II-14"},
    2015: {"I-04", "I-06", "I-07", "II-07", "II-11", "II-15"},
    2016: {"I-06", "I-15", "II-10"},
    2017: {"II-10"},
    2018: {"I-04", "I-15", "II-04", "II-09", "II-12", "II-14"},
    2019: {"I-03", "I-06", "I-13", "I-15", "II-01", "II-07", "II-11", "II-13", "II-15"},
    2020: {"I-01", "I-13", "I-15", "II-04", "II-13", "II-15"},
    2021: {"I-02", "I-09", "I-11", "I-13", "II-02", "II-12", "II-14"},
    2022: {"I-03", "I-08", "I-11", "II-07", "II-11", "II-15"},
    2023: {"I-05", "I-08", "I-12", "II-03", "II-09", "II-12"},
    2024: {"II-05", "II-10"},
    2025: {"I-02", "I-06", "II-01", "II-05", "II-06", "II-12", "II-14"},
}


HMMT_IN_SCOPE: dict[int, set[int]] = {
    2006: {1, 2, 3, 4, 5, 6, 7, 8, 10},
    2007: {2, 3, 4, 6, 7, 8, 9, 10},
    2008: {2, 3, 4, 5, 6, 7, 9, 10},
    2009: {1, 4, 7, 8, 9, 10},
    2010: {1, 2, 6, 9, 10},
    2011: set(),  # identified by statement below; the three PDFs renumber it
    2012: {1, 2, 3, 4},
    2013: {2, 3, 4, 5, 7, 8, 9, 10},
    2014: {1, 2, 3, 4, 6, 7, 8, 9, 10},
    2015: {2, 3, 4, 6},
    2016: {2, 3, 4, 6, 9, 10},
    2017: {1, 4, 5, 6, 7, 9, 10},
    2018: {1, 5, 8, 10},
    2019: {2, 5, 7, 8, 10},
    2020: {2, 4, 5, 6, 7, 8, 9},
    2021: {3, 4, 5, 6, 9},
    2022: {1, 2, 3, 5, 6, 10},
    2023: {1, 2, 4, 5, 7, 8, 10},
    2024: set(range(1, 11)),
    2025: set(range(1, 10)),
}

# Exact statement starts from the 2011 PDFs.  The same statement appears in
# all three tracks, even though its question number differs (8/7, 10/9,
# 12/11, 18/18, 20/20).
HMMT_2011_SCOPE_STARTS = (
    "Let ABCDEF be a regular hexagon of area 1.",
    "Let ABCD be a square of side length 13.",
    "Let ABCDEF be a convex equilateral hexagon",
    "Collinear points A, B, and C are given",
    "Let ω1 and ω2 be two circles that intersect",
)

HMMT_PUBLISHED_ANSWERS = {
    "HMMT-2024-FEB-GEO-01": "5/3",
    # Official HMMT solution PDF, not a value recomputed for this dataset.
    "HMMT-2006-FEB-GEO-02": "9/5",
    "HMMT-2006-FEB-GEO-01": "20+2√2",
    "HMMT-2006-FEB-GEO-03": "31",
    "HMMT-2006-FEB-GEO-04": "27π/40",
    "HMMT-2006-FEB-GEO-05": "22/35",
    "HMMT-2006-FEB-GEO-06": "(2+√2)/4",
    "HMMT-2006-FEB-GEO-07": "3/7",
    "HMMT-2006-FEB-GEO-10": "24",
    "HMMT-2006-FEB-GEO-08": "3/8",
    "HMMT-2014-FEB-GEO-01": "2√21",
    "HMMT-2014-FEB-GEO-02": "169/24",
    "HMMT-2014-FEB-GEO-03": "8√14",
    "HMMT-2014-FEB-GEO-04": "28",
    "HMMT-2014-FEB-GEO-06": "√3",
    "HMMT-2014-FEB-GEO-07": "65/12",
    "HMMT-2014-FEB-GEO-08": "600/73",
    "HMMT-2014-FEB-GEO-09": "92/61",
    "HMMT-2014-FEB-GEO-10": "1235/108",
    "HMMT-2015-FEB-GEO-02": "28/3",
    "HMMT-2015-FEB-GEO-03": "√2/2",
    "HMMT-2015-FEB-GEO-06": "63",
    "HMMT-2015-FEB-GEO-04": "37/76",
    "HMMT-2016-FEB-GEO-02": "14",
    "HMMT-2016-FEB-GEO-04": "7√3/3",
    "HMMT-2016-FEB-GEO-06": "21√3/8",
    "HMMT-2017-FEB-GEO-01": "2/5",
    "HMMT-2017-FEB-GEO-04": "13",
    "HMMT-2018-FEB-GEO-01": "169/10",
    "HMMT-2018-FEB-GEO-05": "8√2/9",
    "HMMT-2019-FEB-GEO-02": "√3",
    "HMMT-2019-FEB-GEO-07": "65/4",
    "HMMT-2019-FEB-GEO-08": "6/7",
    "HMMT-2020-FEB-GEO-02": "40/21",
    "HMMT-2025-FEB-GEO-01": "26",
    "HMMT-2024-FEB-GEO-02": "20",
    "HMMT-2024-FEB-GEO-03": "42",
    "HMMT-2024-FEB-GEO-04": "185",
    "HMMT-2024-FEB-GEO-05": "4√5-√7",
    "HMMT-2024-FEB-GEO-06": "65/3",
    "HMMT-2024-FEB-GEO-07": "8√11",
    "HMMT-2024-FEB-GEO-08": "64(2-√3)",
    "HMMT-2024-FEB-GEO-09": "√38-3",
    "HMMT-2024-FEB-GEO-10": "9√410/5",
    "HMMT-2023-FEB-GEO-02": "2√13",
    "HMMT-2023-FEB-GEO-01": "189",
    "HMMT-2023-FEB-GEO-04": "√5",
    "HMMT-2023-FEB-GEO-05": "42√2",
    "HMMT-2023-FEB-GEO-08": "√111",
    "HMMT-2023-FEB-GEO-10": "11/12",
    "HMMT-2025-FEB-GEO-02": "63",
    "HMMT-2025-FEB-GEO-03": "8√10",
    "HMMT-2025-FEB-GEO-04": "20",
    "HMMT-2025-FEB-GEO-05": "√23-2√3",
    "HMMT-2025-FEB-GEO-06": "9√15",
    "HMMT-2025-FEB-GEO-07": "7/18",
    "HMMT-2025-FEB-GEO-08": "√6",
    "HMMT-2025-FEB-GEO-09": "14+4√37",
    "HMMT-2007-FEB-GEO-02": "2",
    "HMMT-2007-FEB-GEO-03": "2√3",
    "HMMT-2007-FEB-GEO-04": "17",
    "HMMT-2007-FEB-GEO-06": "45√17/17",
    "HMMT-2007-FEB-GEO-07": "8",
    "HMMT-2007-FEB-GEO-08": "55",
    "HMMT-2007-FEB-GEO-09": "∛2-1",
    "HMMT-2007-FEB-GEO-10": "(1+√13)/3",
    "HMMT-2008-FEB-GEO-04": "108",
    "HMMT-2008-FEB-GEO-02": "3",
    "HMMT-2008-FEB-GEO-03": "π-2",
    "HMMT-2008-FEB-GEO-06": "√17",
    "HMMT-2008-FEB-GEO-07": "8",
    "HMMT-2008-FEB-GEO-09": "75/64",
    "HMMT-2008-FEB-GEO-10": "2014024",
    "HMMT-2009-FEB-GEO-07": "6√37/5;21√7585/205",
    "HMMT-2009-FEB-GEO-08": "208",
    "HMMT-2009-FEB-GEO-09": "14",
    "HMMT-2009-FEB-GEO-10": "9",
    "HMMT-2010-FEB-GEO-01": "3π/7",
    "HMMT-2010-FEB-GEO-06": "(8+√6+√2)/4",
    "HMMT-2010-FEB-GEO-10": "2-√3",
    "HMMT-2010-FEB-GEO-09": "70;160",
    "HMMT-2012-FEB-GEO-01": "√17/3",
    "HMMT-2012-FEB-GEO-02": "3√5/4",
    "HMMT-2012-FEB-GEO-03": "540/7",
    "HMMT-2012-FEB-GEO-04": "4√3/3",
    "HMMT-2013-FEB-GEO-02": "2√6",
    "HMMT-2013-FEB-GEO-04": "(-1+√5)/2;(1+√5)/2",
    "HMMT-2013-FEB-GEO-05": "-1/8",
    "HMMT-2013-FEB-GEO-07": "35",
    "HMMT-2013-FEB-GEO-08": "42/13",
}


# Problem numbers read from the official JMO first-stage pages/PDFs.  The
# source image/PDF is retained in every generated row.  The small summaries
# are review notes, not replacement definitions for DSL authoring.
JMO_IN_SCOPE: dict[int, tuple[int, ...]] = {
    2006: (2, 9),
    2007: (1,),
    2008: (2, 11),
    2009: (2,),
    2010: (8, 11),
    2011: (4, 6, 11),
    2012: (1, 2, 7),
    2013: (3, 5, 8),
    2014: (1, 4, 9),
    2015: (2, 8, 11),
    2016: (3, 5, 8),
    2017: (1, 4, 8, 10),
    2018: (3, 6, 9),
    2019: (4, 8, 10),
    2020: (2, 6, 11),
    2021: (2, 3, 7, 10),
    2022: (2, 4, 7, 12),
    2023: (3, 6, 10),
    2024: (3, 6, 9),
    2025: (5, 9, 12),
}

# The rows available in MathNet are used as the exact statement whenever the
# official problem number is known.  Other official rows remain explicitly
# image-verified and untranscribed: this is safer than inventing an English
# sentence from a diagram and prevents accidental DSL drift.
JMO_MATHNET_ALIASES = {
    "JMO-2006-MATHNET-08rb": (2006, 2),
    "JMO-2006-MATHNET-08rn": (2006, 9),
    "JMO-2007-MATHNET-08rq": (2007, 1),
    "JMO-2013-MATHNET-08xe": (2013, 8),
    "JMO-2015-MATHNET-08y6": (2015, 8),
    "JMO-2015-MATHNET-08xw": (2015, 11),
    "JMO-2019-MATHNET-08yk": (2019, 8),
    "JMO-2019-MATHNET-08ya": (2019, 10),
    "JMO-2022-MATHNET-08z8": (2022, 4),
    "JMO-2022-MATHNET-08zb": (2022, 7),
    "JMO-2022-MATHNET-08z4": (2022, 12),
}

# These three rows have machine-readable official PDFs.  The Japanese text
# below was checked against the PDF page, not reconstructed from the answer
# or from a solution.
JMO_OFFICIAL_TEXT = {
    (2006, 2): (
        "正三角形の内部に点Pがあり，Pから各辺に下ろした垂線の長さはそれぞれ1, 2, 3であるとする。"
        "この正三角形の一辺の長さを求めよ。"
    ),
    (2006, 9): (
        "BC=5，CA=7，AB=8である三角形ABCの内部に点Oをとる。三角形OBCの外接円，三角形OCAの外接円，"
        "三角形OABの外接円の半径がすべて等しいとき，その等しい半径を求めよ。"
    ),
    (2007, 1): (
        "凸四角形ABCDは，AB=3，BC=4，CD=5，DA=6，∠ABC=90°をみたす。ABCDの面積を求めよ。"
    ),
    (2013, 8): (
        "凸四角形ABCDがあり，ACとBDが点Xで直交していて，AX=5，BX=6，CX=20が成り立っている。"
        "Aを中心としAXを半径とする円，Bを中心としBXを半径とする円，Cを中心としCXを半径とする円，"
        "Dを中心としDXを半径とする円をそれぞれC1，C2，C3，C4とする。4つの円C1，C2，C3，C4すべてに接する円が存在するとき，"
        "DXを求めよ。ただし，YZで線分YZの長さを表すものとする。"
    ),
    (2015, 8): (
        "平面上に5点A，B，C，D，Pがあり，このうちA，B，C，Dはこの順に同一直線上に並んでいる。"
        "また，AB=BC=CD=6，PB=5，PC=7をみたしている。三角形PACの外接円と三角形PBDの外接円の交点のうちPでない方をQとおくとき，"
        "線分PQの長さを求めよ。ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2015, 11): (
        "三角形ABCの外接円をΓとおく。Γの点Aを含まない方の弧BCの中点をA′，点Bを含まない方の弧CAの中点をB′，"
        "点Cを含まない方の弧ABの中点をC′とおく。三角形AB′C′，三角形A′BC′，三角形A′B′Cの面積がそれぞれ2，3，4のとき，"
        "三角形ABCの面積を求めよ。"
    ),
    (2019, 8): (
        "AB>ACをみたす三角形ABCの内心をIとし，辺AB，ACを1:8に内分する点をそれぞれD，Eとする。"
        "三角形DIEが一辺の長さが1の正三角形であるとき，線分ABの長さを求めよ。"
        "ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2019, 10): (
        "三角形ABCおよび辺AB，AC上の点D，Eについて，AB=6，AC=9，AD=4，AE=6が成り立っている。"
        "また，三角形ADEの外接円と辺BCの交点をそれぞれF，Gとし，三角形BFGCの外接円を考える。"
        "ただし，4点B，F，G，Cはこの順に並んでいる。直線DFとEGが三角形ABCの外接円上で交わるとき，FG/BCの値を求めよ。"
        "なお，XYで線分XYの長さを表すものとする。"
    ),
    (2022, 4): (
        "凸四角形ABCDとその内部の点Pがあり，直線APと直線AD，直線BPと直線CDはそれぞれ直交する。"
        "AB=7，AP=3，BP=6，AD=5，CD=10のとき，三角形ABCの面積を求めよ。"
        "ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2022, 7): (
        "∠BAC=90°，AB=AC=7である直角二等辺三角形ABCがある。辺BC，CA，AB上にそれぞれ点D，E，Fがあり，"
        "∠EDF=90°，DE=5，DF=3をみたしているとき，線分BDの長さを求めよ。"
        "ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2022, 12): (
        "AB=11，AC=10をみたす鋭角三角形ABCがあり，その垂心をH，辺BCの中点をMとする。"
        "三角形ABCの内部の点Pが三角形BHCの外接円上にあり，∠ABP=∠CPM，PM=3をみたしている。"
        "このとき，線分BCの長さを求めよ。ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2020, 6): (
        "平面上に3つの正方形があり、図のようにそれぞれ4つの頂点のうち2つの頂点を他の正方形と共有している。"
        "ここで、最も小さい正方形の対角線を延長した直線は最も大きい正方形の左下の頂点を通っている。"
        "最も小さい正方形と最も大きい正方形の一辺の長さがそれぞれ1, 3であるとき、斜線部の面積を求めよ。"
    ),
    (2021, 2): (
        "下図のような正十角形がある。全体の面積が1のとき、斜線部の面積を求めよ。"
    ),
    (2023, 6): (
        "正六角形が長方形に図のように内接している。斜線部の三角形と四角形の面積がそれぞれ20, 23であるとき、正六角形の面積を求めよ。"
    ),
    (2025, 5): (
        "円に内接する四角形 ABCD が半径 6 の円に外接している。また、半直線 AB と半直線 DC が点 P で交わり、"
        "半直線 AD と半直線 BC が点 Q で交わっている。三角形 PBC, QCD の内接円の半径がそれぞれ 5, 3 であるとき、"
        "BC/CD の値を求めよ。ただし、XY で線分 XY の長さを表す。"
    ),
    (2025, 9): (
        "鋭角三角形 ABC があり、その外心を O とする。A から辺 BC におろした垂線の足を D とすると、"
        "∠AOD = 90°、OD = 4√7 が成立した。D から辺 AB, AC におろした垂線の足をそれぞれ E, F とおくと、"
        "線分 AO と線分 EF が点 P で交わった。AP = 11 のとき、線分 EF の長さを求めよ。ただし、XY で線分 XY の長さを表す。"
    ),
    (2025, 12): (
        "円 Ω に内接する五角形 ABCDE があり、AC = AD および BC ∥ DE をみたしている。また、Ω の A を含まない方の弧 CD 上に点 P をとり、"
        "直線 AB, BC, CD, DE, EA に関して P と対称な点をそれぞれ P1, P2, P3, P4, P5 とすると、"
        "PC : PD = P1P2 : P4P5 = 2 : 3、CD : P2P4 = 4√2 : 11 が成立した。このとき、P1P3/P1P5 の値を求めよ。"
    ),
    (2008, 2): (
        "一辺1の正方形ABCDがある。ADを直径とする円Oを描き，辺AB上の点Eを，直線CEがOの接線となるようにとる。"
        "このとき，三角形CBEの面積を求めよ。"
    ),
    (2008, 11): (
        "凸四角形ABCDはAB=BC=2，CD=2√3，DA=2√5をみたす。また，AC，BDの中点をそれぞれM，Nとすると，MN=√2となる。"
        "このとき，四角形ABCDの面積を求めよ。ただし，XYで線分XYの長さをあらわすものとする。"
    ),
    (2009, 2): (
        "半径2の円O1と半径4の円O2が点Pで外接している。O1，O2の周上にPと異なる点A，Bをそれぞれとるとき，A，P，Bが一直線上に並んでいた。"
        "線分ABの長さが4であるとき，線分PBの長さを求めよ。"
    ),
    (2010, 8): (
        "三角形ABCの内部に点Pがある。AP=√3，BP=5，CP=2，AB:AC=2:1，∠BAC=60°であるとき，三角形ABCの面積を求めよ。"
        "ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2010, 11): (
        "四角形ABCDは∠DAB=110°，∠ABC=50°，∠BCD=70°をみたす。AB，CDの中点をそれぞれM，Nとし，線分MN上に点PをとるとAD=CPとなった。"
        "このとき∠APCの大きさを求めよ。ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2011, 4): (
        "下の図において，点Oは扇形OABの中心である。AQ=5，BQ=6，OQ=PQであるとき，この扇形の半径の長さを求めよ。"
        "ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2011, 6): (
        "∠ABC=90°である三角形ABCの辺BC，CA，AB上に点P，Q，Rがあり，AQ:QC=2:1，AR=AQ，QP=QR，∠PQR=90°が成立している。"
        "CP=1のときARを求めよ。ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2011, 11): (
        "四角形ABCDが，点Oを中心とする円に外接しており，OA=5，OB=6，OC=7，OD=8が成立している。"
        "線分ACの中点をM，線分BDの中点をNとするとき，OM:ONを求めよ。ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2012, 1): (
        "正方形ABCDがある。点P，Q，R，Sがそれぞれ辺AB，BC，CD，DA上にあり，直線PR，BCは平行で，直線SQ，ABは平行である。"
        "PRとSQの交点をZとする。BP=7，BQ=6，DZ=5のとき，正方形ABCDの一辺の長さを求めよ。"
        "ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2012, 2): (
        "下図のように円周上にA，B，C，Dがこの順にあり，Bでの接線と直線ABのなす角は30°，Cでの接線と直線CDのなす角は10°である。"
        "直線AB，DCは平行で，円の中心について反対側にある。このとき∠BDCの大きさを求めよ。"
    ),
    (2012, 7): (
        "三角形ABCの外心をOとする。線分AB上に点D，線分AC上に点Eをとると，線分DEの中点がOと一致した。"
        "AD=8，BD=3，AO=7のとき，CEを求めよ。ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2013, 3): (
        "半径1の円周上にA1，A2，A3，A4，A5がこの順にあり，∠A5A2A4=∠A1A3A5=∠A2A4A1=∠A3A5A2=30°をみたしている。"
        "A2A4とA3A5，A3A5とA4A1，A4A1とA5A2，A5A2とA1A3，A1A3とA2A4の交点をそれぞれB1，B2，B3，B4，B5とするとき，"
        "五角形B1B2B3B4B5の面積を求めよ。"
    ),
    (2013, 5): (
        "相異なる2点P，Qで交わる2円O1，O2がある。点Pにおける円O1の接線が，Pとは異なる点Rで円O2と交わっている。"
        "また，点Qにおける円O2の接線が，Qとは異なる点Sで円O1と交わっている。さらに，直線PRと直線QSが点Xで交わっている。"
        "XR=9，XS=2のとき，円O1の半径は円O2の半径の何倍であるか。ただし，YZで線分YZの長さを表すものとする。"
    ),
    (2014, 1): (
        "円C1が円C2に点Aで内接している。円C2の中心を点Oとする。円C1上に点Pがあり，Pでの円C1の接線はOを通っている。"
        "半直線OPと円C2の交点をQとし，点Aを通る円C1の接線と直線OPの交点をRとする。円C2の半径が9，PQ=QRのとき，線分OPの長さを求めよ。"
        "ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2014, 4): (
        "円周上に6点A，B，C，D，E，Fがこの順にあり，線分AD，BE，CFは一点で交わっている。"
        "AB=1，BC=2，CD=3，DE=4，EF=5のとき，線分FAの長さを求めよ。ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2014, 9): (
        "正方形ABCDがあり，その対角線の交点をOとする。線分OA，OB，OC，OD上にそれぞれ点P，Q，R，Sがあり，OP=3，OQ=5，OR=4をみたしている。"
        "直線ABと直線PQの交点，直線BCと直線QRの交点，直線CDと直線RSの交点が同一直線上にあるとき，線分OSの長さを求めよ。"
        "ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2015, 2): (
        "円周上に3点A，B，Cがあり，点PをBとCにおける円の接線の交点とする。直線ABと直線CPが平行であり，AB=3，BP=4のとき，線分BCの長さを求めよ。"
        "ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2016, 3): (
        "円に内接する六角形ABCDEFについて，半直線ABと半直線DCの交点をP，半直線BCと半直線EDの交点をQ，半直線CDと半直線FEの交点をR，"
        "半直線DEと半直線AFの交点をSとすると，∠BPC=50°，∠CQD=45°，∠DRE=40°，∠ESF=35°であった。"
        "直線BEと直線CFの交点をTとするとき，∠BTCの大きさを求めよ。"
    ),
    (2016, 5): (
        "四角形ABCDはAC=20，AD=16をみたす。線分CD上に点Pをとると，三角形ABPと三角形ACDが合同となった。"
        "三角形APDの面積が28のとき，三角形BCPの面積を求めよ。ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2016, 8): (
        "三角形ABCの内接円をωとする。辺BCとωの接点をDとし，直線ADとωの交点のうちDでない方をXとする。"
        "AX:XD=BC:10，ωの半径が1のとき，線分XDの長さを求めよ。ただし，YZで線分YZの長さを表すものとする。"
    ),
    (2017, 1): (
        "四角形ABCDは∠A=∠B=∠C=30°，AB=4，BC=2√3をみたす。このとき四角形ABCDの面積を求めよ。"
        "ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2017, 4): (
        "相異なる3点D，B，Cは同一直線上にあり，DB=BC=2である。点AはAB=ACをみたし，直線ABと直線DCのそれぞれにおいて，AとDで接する円Γが存在するとする。"
        "Γと直線ABの交点のうちAでない方をEとし，直線CEとΓの交点のうちEでない方をFとするとき，線分EFの長さを求めよ。"
        "ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2017, 8): (
        "三角形ABCの辺BC上に2点D，Eがある。4点B，D，E，Cはこの順に並んでおり，∠BAD=∠ACE，∠ABD=∠CAEであるとする。"
        "三角形ABEの外接円と三角形ADCの外接円のAと異なる交点をXとおき，AXとBCの交点をPとする。"
        "BF=5，CF=6，XD=3のとき，線分XEの長さを求めよ。ただし，PQで線分PQの長さを表すものとする。"
    ),
    (2017, 10): (
        "三角形ABCは∠B=90°，AB=8，BC=3をみたす。辺BC上に点P，辺CA上に点Q，辺AB上に点Rがあり，∠CRP=∠CRQ，∠BPR=∠CPQをみたす。"
        "また，三角形PQRの周の長さは12である。このとき，Qから辺BCにおろした垂線の長さを求めよ。"
        "ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2018, 3): (
        "四角形ABCDが，∠A=∠B=90°，∠C=45°，AC=19，BD=15をみたすとき，その面積を求めよ。"
        "ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2018, 6): (
        "三角形ABCは直角二等辺三角形で，∠A=90°である。その内部に3点X，Y，Zをとったところ，三角形XYZは∠X=90°であるような直角二等辺三角形であり，"
        "点A，XおよびB，Z，YおよびC，X，Zはそれぞれこの順に同一直線上に並んでいた。AB=1，XY=1/4のとき，線分AXの長さを求めよ。"
        "ただし，STで線分STの長さを表すものとする。"
    ),
    (2018, 9): (
        "三角形ABCの内接円が辺BC，CA，ABとそれぞれ点P，Q，Rで，∠A内の傍接円が辺BC，直線CA，ABとそれぞれ点S，T，Uで接している。"
        "三角形ABCの外接円と，直線PQと直線STの交点をD，直線PRと直線SUの交点をEとすると，AI=3，IP=1，PS=2のとき，線分DEの長さを求めよ。"
        "ただし，XYで線分XYの長さを表すものとする。また，三角形ABCの∠A内の傍接円とは，辺BC，直線ABのB側への延長線，および辺ACのC側への延長線に接する円のことをさす。"
    ),
    (2019, 4): (
        "正五角形ABCDEがあり，線分BEと線分ACの交点をFとする。また点Fを通る直線が辺AB，CDとそれぞれG，Hで交わり，BG=4，CH=5が成立つ。"
        "このとき線分AGの長さを求めよ。ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2020, 2): (
        "一辺の長さが1の正六角形ABCDEFがあり，線分ABの中点をGとする。正六角形の内部に点Hをとったところ，三角形CGHは正三角形となった。"
        "このとき三角形EFHの面積を求めよ。"
    ),
    (2020, 11): (
        "円Ωの周上に5点A，B，C，D，Pがこの順にある。点Pを通り直線ABに点Aで接する円と点Pを通り直線CDに点Dで接する円がΩの内部の点Kで交わっている。"
        "また線分AB，CDの中点をそれぞれM，Nとすると，3点A，K，NおよびD，K，Mはそれぞれ同一直線上にあった。AK=5，DK=3，KM=7が成り立つとし，"
        "直線PKとΩの交点のうちPでない方をQとするとき，線分CQの長さを求めよ。ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2021, 3): (
        "AB=ACとなる二等辺三角形ABCの内部に点Pをとり，Pから辺BC，CA，ABにおろした垂線をそれぞれD，E，Fとする。"
        "BD=9，CD=5，PE=2，PF=5のとき，辺ABの長さを求めよ。ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2021, 7): (
        "三角形ABCの辺BC上に点P，Qがあり，三角形ACPの垂心と三角形ABQの垂心は一致している。AB=10，AC=11，BP=5，CQ=6のとき，辺BCの長さを求めよ。"
        "ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2021, 10): (
        "三角形ABCの辺AB，AC上にそれぞれ点D，Eがあり，4点D，B，C，Eは同一円周上にある。また，四角形DBCEの内部に点Pがあり，∠BDP=∠BPC=∠PECをみたしている。"
        "AB=9，AC=11，DP=1，EP=3のとき，BP/CPの値を求めよ。ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2022, 2): (
        "辺ADと辺BCが平行で，角Bと角Cが鋭角であるような台形ABCDに半径3の円が内接している。AB=7，CD=8のとき台形ABCDの面積を求めよ。"
        "ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2023, 3): (
        "一辺の長さが3である正三角形ABCの辺BC，CA，AB上にそれぞれ点D，E，Fがあり，BD=1，∠ADE=∠DEF=60°をみたしている。"
        "このとき，線分AFの長さを求めよ。ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2023, 10): (
        "鋭角三角形ABCがあり，Aから辺BCにおろした垂線の足をD，辺ACの中点をMとする。線分BM上に点Pを，∠PAM=∠MBAをみたすようにとる。"
        "∠BAP=41°，∠PDB=115°のとき，∠BACの大きさを求めよ。"
    ),
    (2024, 3): (
        "一辺の長さが10の正三角形ABCがある。Aを通る円が辺BC（端点を除く）と点Xで接し，辺AB，ACとそれぞれAでない点D，Eで交わっている。"
        "BX>CX，AD+AE=13がともに成立つとき，線分BXの長さを求めよ。ただし，PQで線分PQの長さを表すものとする。"
    ),
    (2024, 6): (
        "AB=AC=5である二等辺三角形ABCの辺AB上にAD=3をみたす点Dが，辺BC上（端点を除く）に点Eがある。"
        "点Eを通り直線ABに点Bで接する円をωとすると，ωは三角形ADEの外接円に接した。ωと直線AEの交点のうちEでない方をFとすると，CF=10が成り立った。"
        "このとき，辺BCの長さを求めよ。ただし，XYで線分XYの長さを表すものとする。"
    ),
    (2024, 9): (
        "円に内接する四角形ABCDがあり，AB=7，BC=18をみたしている。∠CDAの二等分線と辺BCが点Eで交わっており，また線分DE上の点Fが∠AED=∠FCDをみたしている。"
        "BE=5，EF=3のとき，線分DFの長さを求めよ。ただし，XYで線分XYの長さを表すものとする。"
    ),
}

# Clause ledgers for the initial seed cases. Keeping these in the audit file
# makes the source-to-DSL correspondence inspectable even after the
# exhaustive audit is regenerated; later cases carry their own ledger in the
# JSON file and are copied into the regenerated audit row below.
EXISTING_CLAUSE_LEDGERS = {
    "AIME-2006-I-01": [
        {"source": "quadrilateral ABCD", "dsl": "A,B,C,D construction plus convex-branch guard", "kind": "construction/guard"},
        {"source": "angle B is a right angle", "dsl": "Angle(A,B,C)=pi/2", "kind": "constraint"},
        {"source": "AC perpendicular CD", "dsl": "Angle(A,C,D)=pi/2", "kind": "constraint"},
        {"source": "AB=18, BC=21, CD=14", "dsl": "Distance constraints; B and C use the given right-angle gauge", "kind": "constraint"},
        {"source": "perimeter ABCD", "dsl": "sum of four source side distances", "kind": "answer"},
    ],
    "AIME-2008-II-05": [
        {"source": "trapezoid ABCD with BC parallel AD", "dsl": "B,C share y=h and A,D share y=0; direct Distance/angle constraints", "kind": "construction/constraint"},
        {"source": "BC=1000 and AD=2008", "dsl": "Distance(B,C)=1000 and Distance(A,D)=2008", "kind": "constraint"},
        {"source": "angle A=37 and angle D=53", "dsl": "Angle(D,A,B)=37*pi/180 and Angle(C,D,A)=53*pi/180", "kind": "constraint"},
        {"source": "M,N midpoints", "dsl": "M=Midpoint(B,C), N=Midpoint(A,D)", "kind": "construction"},
        {"source": "MN", "dsl": "Distance(M,N)", "kind": "answer"},
    ],
    "AIME-2011-II-02": [
        {"source": "square ABCD", "dsl": "A,B,C,D coordinate construction with side parameter s", "kind": "construction"},
        {"source": "E on AD and F on BC", "dsl": "E=Point(0,t), F=Point(s,u), with 0<t,u<s guards", "kind": "construction/guard"},
        {"source": "BE=EF=FD=30", "dsl": "three direct Distance constraints", "kind": "constraint"},
        {"source": "area ABCD", "dsl": "Area(A,B,C,D)", "kind": "answer"},
    ],
    "HMMT-2006-FEB-GEO-02": [
        {"source": "ABC is a scalene right triangle", "dsl": "Angle(A,B,C)=pi/2; non-equality guard; By>0 nondegenerate branch", "kind": "constraint/guard"},
        {"source": "P on hypotenuse AC", "dsl": "A,P,C are the fixed ordered carrier points (AP=1, PC=2)", "kind": "construction/gauge"},
        {"source": "angle ABP=45 degrees", "dsl": "Angle(A,B,P)=pi/4", "kind": "constraint"},
        {"source": "AP=1 and CP=2", "dsl": "Distance(A,P)=1 and Distance(P,C)=2", "kind": "constraint"},
        {"source": "area of ABC", "dsl": "Area(A,B,C)", "kind": "answer"},
    ],
    "HMMT-2006-FEB-GEO-08": [
        {"source": "right angle at B", "dsl": "Angle(A,B,C)=pi/2", "kind": "constraint"},
        {"source": "D lies on side BC", "dsl": "D=Point(Dx,0), 0<Dx<Cx", "kind": "construction/guard"},
        {"source": "3 angle BAD = angle BAC", "dsl": "3*Angle(B,A,D)=Angle(B,A,C)", "kind": "constraint"},
        {"source": "AC=2 and CD=1", "dsl": "Distance(A,C)=2 and Distance(C,D)=1", "kind": "constraint"},
        {"source": "BD", "dsl": "Distance(B,D)", "kind": "answer"},
    ],
    "HMMT-2025-FEB-GEO-01": [
        {"source": "equilateral ABC", "dsl": "Distance(A,B)=Distance(B,C)=Distance(A,C)", "kind": "constraint"},
        {"source": "equilateral DEF", "dsl": "Distance(D,E)=Distance(E,F)=Distance(D,F)", "kind": "constraint"},
        {"source": "B,E,F,C lie on a line in this order", "dsl": "all four carrier points have y=0; BE/EF/FC constraints and order guards", "kind": "construction/constraint/guard"},
        {"source": "D inside ABC", "dsl": "three positive subareas and their sum equal Area(A,B,C)", "kind": "membership predicate"},
        {"source": "BE=14, EF=15, FC=16", "dsl": "three direct Distance constraints", "kind": "constraint"},
        {"source": "AD", "dsl": "Distance(A,D)", "kind": "answer"},
    ],
    "JMO-2022-PRE-04": [
        {"source": "convex quadrilateral ABCD", "dsl": "construction plus convexity guard", "kind": "construction/guard"},
        {"source": "P is inside ABCD", "dsl": "four positive triangle areas sum to Area(A,B,C,D)", "kind": "membership predicate"},
        {"source": "AP perpendicular AD", "dsl": "Perpendicular(Line(A,P), Line(A,D))=0", "kind": "constraint"},
        {"source": "BP perpendicular CD", "dsl": "Perpendicular(Line(B,P), Line(C,D))=0", "kind": "constraint"},
        {"source": "AB=7, AP=3, BP=6, AD=5, CD=10", "dsl": "direct Distance constraints", "kind": "constraint"},
        {"source": "area ABC", "dsl": "Area(A,B,C)", "kind": "answer"},
    ],
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def aime_key(row: dict) -> str:
    problem_id = row["problem_id"]
    m = re.search(r"(?:AIME-)?(\d{4})-([IV]+)-0?(\d+)$", problem_id)
    if not m:
        raise ValueError(f"unexpected AIME id: {problem_id}")
    return f"{m.group(2)}-{int(m.group(3)):02d}"


def hmmt_number(row: dict) -> int:
    return int(re.search(r"-(\d{2})$", row["problem_id"]).group(1))


def official_image_url(year: int, problem: int) -> str:
    if year <= 2023:
        exam = year - 1990
        return f"https://www.imojp.org/archive/mo{year}/jmo{year}/problems/jmo{exam}yq.html#problem-{problem}"
    exam = year - 1990
    return f"https://www.imojp.org/archive/mo{year}/problems/jmo{exam}yqa.pdf#problem-{problem}"


def jmo_source_note(year: int, problem: int) -> str:
    return (
        f"JMO {year} 予選 第{problem}問。公式問題画像/PDFを目視確認済み。"
        "DSL転記ではこの原文と図を照合し、未確認の数値・順序・内外関係を補わない。"
    )


def classify(row: dict) -> tuple[str, str, str, str]:
    contest = row.get("contest")
    year = int(row.get("year"))
    pid = row["problem_id"]
    if contest == "AIME":
        key = aime_key(row)
        if key in AIME_IN_SCOPE[year]:
            return "in_scope", "manual full-statement review: finite 2D labeled configuration and scalar target", f"AIME-{year}-{key}", "manual_read"
        return "out_scope", "manual full-statement review: arithmetic/discrete, 3D, optimization/locus, or non-geometric target", f"AIME-{year}-{key}", "manual_read"
    if contest == "HMMT":
        if year == 2011:
            statement = row.get("statement", "")
            for idx, start in enumerate(HMMT_2011_SCOPE_STARTS):
                if statement.startswith(start):
                    keys = ["regular-hexagon", "square", "equilateral-hexagon", "collinear-circumcircle", "two-circles-tangent-line"]
                    key = f"HMMT-2011-{keys[idx]}"
                    return "in_scope", "manual full-statement review: finite 2D labeled configuration and scalar target", key, "manual_read"
            return "out_scope", "manual full-statement review: discrete/optimization/continuous locus/non-2D target", f"HMMT-2011-{hmmt_number(row):02d}", "manual_read"
        number = hmmt_number(row)
        if number in HMMT_IN_SCOPE[year]:
            return "in_scope", "manual full-statement review: finite 2D labeled configuration and scalar target", f"HMMT-{year}-FEB-GEO-{number:02d}", "manual_read"
        return "out_scope", "manual full-statement review: optimization/locus, continuous family, 3D, probability, or non-scalar target", f"HMMT-{year}-FEB-GEO-{number:02d}", "manual_read"
    if contest == "JMO preliminary":
        if pid.endswith("OFFICIAL-LINKS"):
            return "metadata_only", "annual official index link; not a problem row", pid, "index_only"
        alias = JMO_MATHNET_ALIASES.get(pid)
        if alias:
            y, n = alias
            return "in_scope", "manual visual check against official page; MathNet text retained as auxiliary exact statement", f"JMO-{y}-PRE-{n:02d}", "manual_read"
        # Unmatched MathNet rows are supplemental material, not silently
        # promoted to a first-stage problem.
        return "out_scope", "manual source check: MathNet supplement is not identified as an official first-stage row in the 2006--2025 scan set", pid, "manual_read"
    return "out_scope", "unknown source", pid, "manual_read"


def make_official_rows(existing: list[dict]) -> list[dict]:
    by_alias = {k: row for k, row in ((r["problem_id"], r) for r in existing) if k in JMO_MATHNET_ALIASES}
    rows = []
    for year, numbers in JMO_IN_SCOPE.items():
        for number in numbers:
            canonical = f"JMO-{year}-PRE-{number:02d}"
            matched = next((row for pid, row in by_alias.items() if JMO_MATHNET_ALIASES[pid] == (year, number)), None)
            # When the official scan has been transcribed, it is the
            # canonical source statement.  MathNet remains an auxiliary row
            # (and may still provide the published answer), but must not
            # replace the official wording in the canonical DSL case.
            if (year, number) in JMO_OFFICIAL_TEXT:
                statement = JMO_OFFICIAL_TEXT[(year, number)]
                answer = matched.get("answer") if matched else None
                source_kind = "JMO-official-image-manual-read"
                source_url = official_image_url(year, number)
                statement_status = "official_pdf_text_checked" if year >= 2024 else "official_image_text_manually_transcribed"
            elif matched:
                statement = matched.get("statement", "")
                answer = matched.get("answer")
                source_kind = "JMO-official-image-plus-MathNet-text"
                source_url = matched.get("source_url")
                statement_status = "text_available_and_official_problem_number_checked"
            else:
                statement = JMO_OFFICIAL_TEXT.get((year, number), jmo_source_note(year, number))
                answer = {(2025, 5): "15/11", (2025, 9): "2√61", (2025, 12): "√37/10"}.get((year, number))
                source_kind = "JMO-official-image-manual-read"
                source_url = official_image_url(year, number)
                if (year, number) in JMO_OFFICIAL_TEXT:
                    statement_status = "official_pdf_text_checked" if year >= 2024 else "official_image_text_manually_transcribed"
                else:
                    statement_status = "official_image_verified_not_transcribed"
            rows.append(
                {
                    "problem_id": canonical,
                    "contest": "JMO preliminary",
                    "year": year,
                    "round": f"{year} preliminary problem {number}",
                    "source_kind": source_kind,
                    "source_url": source_url,
                    "statement": statement,
                    "answer": answer,
                    "topic_evidence": "manual visual reading of official question page",
                    "extraction_status": "manual_read",
                    "scope_status": "in_scope",
                    "scope_reason": "finite 2D labeled configuration and scalar target; verified from official problem image/PDF",
                    "manual_audit": True,
                    "statement_status": statement_status,
                    "dedupe_key": canonical,
                    "dsl_path": f"dsl/{canonical}.json",
                }
            )
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    args = ap.parse_args()
    root = args.root
    all_rows = read_jsonl(root / "all_geometry.jsonl")
    # Drop canonical JMO rows from a previous run before rebuilding them.
    all_rows = [r for r in all_rows if not re.fullmatch(r"JMO-\d{4}-PRE-\d{2}", r["problem_id"])]
    official_rows = make_official_rows(all_rows)
    all_rows.extend(official_rows)

    audit_rows: list[dict] = []
    existing_dsl_files = {p.name for p in (root / "dsl").glob("*.json")}
    for row in all_rows:
        status, reason, dedupe_key, audit_status = classify(row)
        if row["problem_id"].startswith("JMO-") and re.fullmatch(r"JMO-\d{4}-PRE-\d{2}", row["problem_id"]):
            status = "in_scope"
            reason = "finite 2D labeled configuration and scalar target; verified from official problem image/PDF"
            dedupe_key = row["problem_id"]
            audit_status = "manual_read"
        row["scope_status"] = status
        row["scope_reason"] = reason
        row["manual_audit"] = True
        row["dedupe_key"] = dedupe_key
        if status == "in_scope":
            # AIME 2025's source API uses ids such as ``2025-I-2`` while the
            # canonical dataset filename retains the contest prefix and
            # zero-padding (``AIME-2025-I-02``).  Match both the source id and
            # the dedupe key, without changing the source row itself.
            dsl_name = next(
                (name for name in (f"{row['problem_id']}.json", f"{row['dedupe_key']}.json") if name in existing_dsl_files),
                None,
            )
            if dsl_name:
                row["dsl_path"] = f"dsl/{dsl_name}"
                row["dsl_status"] = "ready"
            elif row.get("statement_status") == "official_image_verified_not_transcribed":
                row["dsl_path"] = None
                row["dsl_status"] = "pending_official_image_transcription"
            else:
                row["dsl_path"] = None
                row["dsl_status"] = "pending_source_faithful_encoding"
        elif status != "metadata_only":
            row["dsl_path"] = None
            row["dsl_status"] = "not_applicable"
        else:
            row["dsl_path"] = None
            row["dsl_status"] = "metadata_only"
        row["manual_audit_basis"] = audit_status
        audit = {
            "problem_id": row["problem_id"],
            "contest": row["contest"],
            "year": row["year"],
            "source_statement": row.get("statement", ""),
            "published_answer": row.get("answer") or HMMT_PUBLISHED_ANSWERS.get(row["problem_id"]),
            "answer_source_url": (
                f"https://hmmt-archive.s3.amazonaws.com/tournaments/{row['year']}/feb/geo/solutions.pdf"
                if row["problem_id"] in HMMT_PUBLISHED_ANSWERS else None
            ),
            "source_url": row.get("source_url"),
            "source_kind": row.get("source_kind"),
            "scope_status": status,
            "scope_reason": reason,
            "dedupe_key": dedupe_key,
            "manual_audit": True,
            "statement_status": row.get("statement_status", "full_statement_read"),
            "dsl_path": row.get("dsl_path"),
            "dsl_status": row.get("dsl_status"),
        }
        if row["problem_id"] in EXISTING_CLAUSE_LEDGERS:
            audit["clause_ledger"] = EXISTING_CLAUSE_LEDGERS[row["problem_id"]]
        # Every runnable case carries its own source-to-DSL ledger.  Copy it
        # into the audit row so the regenerated matrix remains inspectable for
        # cases added after the initial seven, including canonical AIME-2025
        # filenames matched through the dedupe key.
        if row.get("dsl_path"):
            case_path = root / row["dsl_path"]
            if case_path.exists():
                case = json.loads(case_path.read_text(encoding="utf-8"))
                if case.get("source_statement"):
                    audit["dsl_source_statement"] = case["source_statement"]
                if case.get("clause_ledger"):
                    audit["clause_ledger"] = case["clause_ledger"]
        audit_rows.append(audit)

    # Keep source-specific files in sync.  The canonical JMO rows are added to
    # the JMO file; the old annual-link rows remain metadata-only.
    by_id = {row["problem_id"]: row for row in all_rows}
    for name in ("aime_geometry.jsonl", "hmmt_geometry.jsonl", "jmo_geometry.jsonl"):
        path = root / name
        if not path.exists():
            continue
        rows = read_jsonl(path)
        if name == "jmo_geometry.jsonl":
            rows = [r for r in rows if not re.fullmatch(r"JMO-\d{4}-PRE-\d{2}", r["problem_id"])] + official_rows
        for row in rows:
            updated = by_id.get(row["problem_id"])
            if updated:
                row.update({k: updated[k] for k in ("scope_status", "scope_reason", "manual_audit", "dedupe_key", "dsl_path", "dsl_status", "manual_audit_basis") if k in updated})
        write_jsonl(path, rows)
    write_jsonl(root / "all_geometry.jsonl", all_rows)
    write_jsonl(root / "manual_audit.jsonl", audit_rows)

    # The inventory intentionally includes metadata-only and duplicate source
    # rows, while totals use unique dedupe keys and only actual problem rows.
    inventory = [
        {
            "problem_id": row["problem_id"],
            "contest": row["contest"],
            "year": row["year"],
            "scope_status": row["scope_status"],
            "scope_reason": row["scope_reason"],
            "dedupe_key": row["dedupe_key"],
            "manual_audit": True,
            "statement_status": row.get("statement_status", "full_statement_read"),
            "dsl_path": row.get("dsl_path"),
            "dsl_status": row.get("dsl_status"),
        }
        for row in all_rows
    ]
    write_jsonl(root / "scope_inventory.jsonl", inventory)

    unique_scope = {r["dedupe_key"] for r in inventory if r["scope_status"] == "in_scope"}
    unique_scope_by_contest = {}
    unique_scope_by_year_contest: dict[str, set[str]] = {}
    for r in inventory:
        if r["scope_status"] == "in_scope":
            unique_scope_by_contest[r["contest"]] = unique_scope_by_contest.get(r["contest"], set()) | {r["dedupe_key"]}
            key = f"{r['year']}/{r['contest']}"
            unique_scope_by_year_contest[key] = unique_scope_by_year_contest.get(key, set()) | {r["dedupe_key"]}
    dsl_files = {p.name for p in (root / "dsl").glob("*.json")}
    ready_paths = {
        (r.get("dsl_path") or "")
        for r in inventory
        if r["scope_status"] == "in_scope"
        and (r["problem_id"] + ".json" in dsl_files or r["dedupe_key"] + ".json" in dsl_files)
    }
    summary_path = root / "extraction_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    summary.setdefault("counts", {})["all_records"] = len(all_rows)
    summary["counts"]["jmo_official_in_scope_problem_rows"] = sum(len(v) for v in JMO_IN_SCOPE.values())
    summary["scope_count"] = len(unique_scope)
    summary["scope_count_status"] = "exhaustively_audited"
    summary["scope_count_by_contest"] = {k: len(v) for k, v in sorted(unique_scope_by_contest.items())}
    summary["scope_count_by_year_and_contest"] = {k: len(v) for k, v in sorted(unique_scope_by_year_contest.items())}
    summary["scope_source_rows_including_hmmt_2011_duplicates"] = sum(1 for r in inventory if r["scope_status"] == "in_scope")
    summary["dsl_ready_count"] = len(ready_paths)
    reference_only_files = {
        p.name
        for p in (root / "dsl").glob("*.json")
        if str(json.loads(p.read_text(encoding="utf-8")).get("solver_coverage", "")).startswith("reference_only")
    }
    summary["dsl_file_count"] = len(dsl_files)
    summary["dsl_runnable_count"] = len(dsl_files - reference_only_files)
    summary["current_solver_scope_files"] = len(dsl_files - reference_only_files)
    summary["dsl_reference_only_count"] = len(reference_only_files)
    summary["dsl_unrunnable_count"] = len(reference_only_files)
    ready_dedupe = {
        r["dedupe_key"]
        for r in inventory
        if r["scope_status"] == "in_scope" and r.get("dsl_path") in ready_paths
    }
    runnable_dedupe = {
        r["dedupe_key"]
        for r in inventory
        if r["scope_status"] == "in_scope"
        and r.get("dsl_path") in ready_paths
        and Path(r["dsl_path"]).name not in reference_only_files
    }
    summary["current_solver_scope_unique"] = len(runnable_dedupe)
    summary["dsl_pending_count"] = len(unique_scope) - len(ready_dedupe)
    summary["manual_audit_count"] = len(audit_rows)
    summary["manual_audit_problem_ids"] = sorted(r["problem_id"] for r in audit_rows)
    summary["manual_dsl_count_lower_bound"] = len(ready_paths)
    summary["scope_policy"] = "Unique dedupe_key rows manually read from source statements/images; HMMT 2011 repeated track PDFs do not inflate the total."
    summary["notes"] = [
        "Every AIME and HMMT candidate row in the extracted 2006--2025 window received a manual in_scope/out_scope decision.",
        "JMO official first-stage problem numbers were manually checked from the official page/PDF for every year; 56 unique rows are in scope.",
        "All 56 canonical JMO in-scope rows have manually checked source text (50 transcribed from official images and 6 from official PDFs); 11 MathNet rows remain separately marked as supplemental aliases/source rows, and non-scope image metadata is not promoted into the corpus.",
        "dsl_ready_count is the number of JSON files currently present (including explicit reference_only records); dsl_runnable_count is the subset executable by the current IR.",
    ]
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "all_records": len(all_rows),
        "scope_count": len(unique_scope),
        "scope_count_by_contest": {k: len(v) for k, v in sorted(unique_scope_by_contest.items())},
        "source_scope_rows": sum(1 for r in inventory if r["scope_status"] == "in_scope"),
        "dsl_ready_count": len(ready_paths),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

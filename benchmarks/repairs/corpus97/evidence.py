"""Source locators and translation decisions, independent of solver outcomes."""

from __future__ import annotations

import json
from pathlib import Path

NOTES = {
    "AIME-2008-I-02": ("共有部分は高さ10の台形。三角形の高さhを変数にし、共有面積80を条件とする。"),
    "AIME-2010-I-13": (
        "252幅の長方形と半径126の半円。切断線の一方の領域を台形"
        "＋扇形−三角形で表し、面積比1:2の両向きを許す。"
    ),
    "AIME-2013-I-12": (
        "60度・45度の三角形に単位正六角形を配置。全頂点の包含とE/Fの少なくとも一方の接触を条件にし、接触頂点を答えから選ば"
        "ない。"
    ),
    "AIME-2014-I-15": (
        "3-4-5三角形の直角はB。旧固定座標は辺長条件と矛盾していた。F/Gは辺AC上の異なる交点。"
    ),
    "AIME-2018-I-15": (
        "4つの弧を3通りに並べ替える。対角線角の正弦を各入力値に対応させ、共通面積を求める。"
    ),
    "AIME-2018-II-04": (
        "図の六つの三角形の面積和。自己交差する頂点列の符号付き面積ではなく、各領域を明示して足す。"
    ),
    "AIME-2019-I-13": ("原文にないfy>0を除去。Fは固定したCと反対側に現れる。"),
    "AIME-2019-II-13": (
        "面積1の円の8等分点。扇形−中心三角形＋Pを頂点とする有向三角形で領域面積を表す。参照は面積自体であり、整数形式のnでは"
        "ない。"
    ),
    "AIME-2021-II-12": ("原文はtanの絶対値。根拠のない鋭角制約を除去しabs(tan(...))へ修正。"),
    "HMMT-2008-FEB-GEO-05": (
        "折り返す前の凧形を軸対称座標で表す。円の中心となる頂点を4通りとも条件に含め、角144度と折り線の角二等分条件を課す。"
    ),
    "HMMT-2009-FEB-GEO-01": (
        "5×8長方形の二つの折り線についてReflectを使い、上の両頂点の移動先が一致することを課す。"
    ),
    "HMMT-2009-FEB-GEO-04": (
        "直角を持つ凧形をBC=1で相似正規化。内心を中心線上に置き、"
        "拡大した凧形と接点間の平行条件を表す。"
    ),
    "HMMT-2010-FEB-GEO-02": (
        "高さ1の長方形を対角線で折る。Reflectによる折り返しと和集合五角形の面積を直接使用する。"
    ),
    "HMMT-2011-FEB-ALGGEO-18": (
        "原文のcollinearは点の順序を指定しない。bx>0,cx>0を除去。公式の7に加え35/11が成立することを独立な"
        "厳密座標計算で確認。READMEの全分岐導出参照。"
    ),
    "HMMT-2011-equilateral-hexagon": (
        "辺長を1に相似正規化し、AD/BC/EFの平行性、凸性、最小内角4度を条件にする。垂心三角形の最小角を度数で返す。"
    ),
    "HMMT-2013-FEB-GEO-09": (
        "公式問題・解説PDFで欠けた根号を確認。BA/DA=2sqrt(2)/3、CD=7sqrt(5)/3、"
        "DE=15sqrt(2)/4。2026-08-30に公式アーカイブから再取得して保存済みhashとの一致を確認。"
        "角の和300度も原文どおりで、通常角では条件が矛盾する。余弦定理による独立証明を追加。"
        "公式訂正版は見つからず、意図を推測したDSL改変は行わない。"
        "HMMT_2013_GEO_09_SOURCE_CHECK.mdを参照。"
    ),
    "HMMT-2016-FEB-GEO-03": (
        "回転対称性により、求める二領域の面積差は(正三角形面積−円面積)/3。差なので負値を許す。"
    ),
    "HMMT-2016-FEB-GEO-10": (
        "ABは3ではなくsqrt(3)。角の内部二等分線上の中心構成を維持し、"
        "mixtilinear circleの内接条件を明示。"
    ),
    "HMMT-2017-FEB-GEO-05": (
        "四辺の支持直線に接するだけでなく、内心が凸四角形の内部にあることを課す。"
    ),
    "HMMT-2017-FEB-GEO-07": (
        "接する半径17/7の円、接点Qでの接線、AQ=3BQを構成。A/BはQからの距離で選択、RはP以外の交点。"
    ),
    "HMMT-2017-FEB-GEO-10": (
        "原文の求値は積ではなくIM/IN。分数線の抽出漏れを修正し、内心の内部性も追加。"
    ),
    "HMMT-2018-FEB-GEO-10": ("KはB以外の交点。旧selectorなしの曖昧なIntersectをexclude=Bへ修正。"),
    "HMMT-2019-FEB-GEO-05": (
        "DOは3ではなくsqrt(3)。公式解説も鋭角条件が明記されていないことを注記しているため、二つの面積を参照集合とする。"
    ),
    "HMMT-2020-FEB-GEO-04": (
        "旧Ratio/3引数TangentAtPointの未移植問題を公開DSLで再構成。長方形内の四角形・三角形の内接円がBE"
        "の同じ点に接する条件。"
    ),
    "HMMT-2020-FEB-GEO-05": (
        "公式の6回の回転による分割を利用。求める領域の6倍は辺長4の正六角形から半径3の円を引いた面積。元の辺長2の六角形面積の"
        "4倍を用いる。"
    ),
    "HMMT-2020-FEB-GEO-06": (
        "AF=6でCA方向へ延長したFのy座標は13ay/7。円の面積はpi*r**2であり(pi*r)**2ではない。"
    ),
    "HMMT-2020-FEB-GEO-07": (
        "原点から等距離の二交点にnear=originを使うと常にtie。座標辞書順の一方をAにし、反対側は対称で同じ求値。"
    ),
    "HMMT-2021-FEB-GEO-09": (
        "原文にないAB=5の固定を変数bへ戻す。Pが対角線上の線分に属することと凸性を明示。"
    ),
    "HMMT-2022-FEB-GEO-02": (
        "4長方形を逐次射影で構成。和集合を長方形面積和−3隣接重複三角形で表す。別実装の全15交差の包除で面積30を検算。"
    ),
    "HMMT-2022-FEB-GEO-10": (
        "求値OPそのものは32-8sqrt(15)。公式の整数表示103360はsqrt(1024)-sqrt(960)の係数表"
        "示に由来する。"
    ),
    "JMO-2008-PRE-11": (
        "原文の凸四角形条件を復元。AC**2の二つの候補のうち非凸な配置を除く。独立厳密計算を添付。"
    ),
    "JMO-2009-PRE-02": (
        "原文のP以外の交点A/BをIntersect(...,exclude=P)で直接構成。"
        "自由点＋非一致条件でもA→Pの擬似解4が受理された診断v3を保存。"
        "これはsolver側の残存問題であり、DSL変更で検証器が直ったとは扱わない。"
        "参照8/3は相似比−2から独立導出し、余剰解は参照に加えない。"
    ),
    "JMO-2010-PRE-11": (
        "単純四角形を明示。旧OCRでは条件が欠けていたが、公開DSLのAM:CN=MP:NPとAP=CPは公式問題画像と一致。"
    ),
    "JMO-2011-PRE-04": (
        "AB=11の中垂線上に中心O=(11/2,h)。Q=(5,0)がOPの中点なのでP=(9/2,-h)。旧中心x=5の誤り"
        "を修正。"
    ),
    "JMO-2011-PRE-06": ("直角はB。Qは辺CAを2:1に分ける点で、旧DSLの別の辺上の点ではない。"),
    "JMO-2011-PRE-11": (
        "四辺の直線への等距離だけでなく、内心Oの内部性を明示。比の独立な反転による導出を添付。"
    ),
    "JMO-2013-PRE-05": ("p<0をp>0へ訂正。方べきからp**2=2q, q**2=9pであり旧符号は不可能。"),
    "JMO-2014-PRE-09": (
        "根拠のないs>8を除去。正の長さとP/Q/R/Sが各線分OA/OB/OC/OD上であることを明示。"
    ),
    "JMO-2016-PRE-05": ("単純四角形を明示。既存by>0の配置は原文の有効な凸配置を表す。"),
    "JMO-2016-PRE-08": (
        "原文は内接円半径1、AX:XD:BC=1:3:10。根拠のない周長20を除去し、半径とBCの比を復元。"
    ),
    "JMO-2017-PRE-01": (
        "単純四角形を明示。凹な頂点を持つ正しい配置を排除するConvexPolygonは用いない。"
    ),
    "JMO-2017-PRE-04": (
        "AB=ACの二等辺三角形なのでB=(0,0),C=(2,0)に対しA=(1,h)。旧A=(0,h)を修正。接する辺は公式"
        "画像のAC。"
    ),
    "JMO-2020-PRE-06": (
        "大小の正方形と斜めの中正方形を、辺長3/1、対角線上の整列、"
        "包含条件から構成。塗り部分を三角形WVSで表す。"
    ),
    "JMO-2021-PRE-07": (
        "c>11とQ/Pの順序の仮定を除去。原文はP/Qの順序を指定"
        "しておらず、BC上に取れるためのc>6のみ保持。"
    ),
    "JMO-2021-PRE-10": ("原文にないex>0を除去。原文が許す鈍角配置を排除しない。"),
    "JMO-2022-PRE-02": ("原文でB/Cは鋭角。正の水平成分および内心の内部性を追加。"),
    "JMO-2023-PRE-06": (
        "図の六角形の位置に合わせpi/2<phi<2*pi/3へ訂正。旧範囲ではH1/H4が長方形からはみ出す。包含も条件として"
        "明示。"
    ),
    "JMO-2023-PRE-10": "原文の鋭角三角形条件を追加。",
    "JMO-2025-PRE-05": ("内心の内部性と、四本の半直線の前方交点条件を明示。"),
    "JMO-2025-PRE-09": ("原文の鋭角三角形、PがAO/EFの両線分に属することを復元。"),
}
NOTES["HMMT-2011-collinear-circumcircle"] = NOTES["HMMT-2011-FEB-ALGGEO-18"]

ALIASES = {
    "HMMT-2011-regular-hexagon": ("combgeo", 7),
    "HMMT-2011-square": ("combgeo", 9),
    "HMMT-2011-equilateral-hexagon": ("combgeo", 11),
    "HMMT-2011-two-circles-tangent-line": ("combgeo", 20),
    "HMMT-2011-collinear-circumcircle": ("alggeo", 18),
}


def ledger_rows(before, repaired):
    manifest = json.loads(Path(__file__).with_name("source-manifest.json").read_text())
    sources = {entry["path"]: entry for entry in manifest if "sha256" in entry}
    result = []
    for old in before:
        identifier = old["id"]
        row = repaired[identifier]
        year = int(identifier.split("-")[1])
        method = "official_published_answer"
        if identifier.startswith("AIME"):
            names = [identifier.lower() + "-solution.html"]
            locator = (
                f"{year} AIME {identifier.split('-')[2]}, problem {int(identifier.split('-')[3])}"
            )
            method = "authored_solution_raw_target"
        elif identifier.startswith("HMMT"):
            round_name, number = ALIASES.get(identifier, ("geo", 0))
            if not number:
                round_name, number = identifier.split("-")[3].lower(), int(identifier.split("-")[4])
            names = [f"hmmt-{year}-{round_name}-{kind}.pdf" for kind in ("problems", "solutions")]
            locator = f"{year} February {round_name}, problem {number}"
        else:
            number = int(identifier.split("-")[3])
            locator = f"第{year - 1990}回 JMO 予選 第{number}問"
            if year <= 2022:
                names = sorted(n for n in sources if n.startswith(f"jmo-{year}-jmo") and "yq" in n)
                if year >= 2012:
                    names.append(f"jmo-{year}-jmo{year - 1990}ya.jpg")
                else:
                    method = "independent_geometric_derivation"
            else:
                names = [f"jmo-{year}.pdf"]
                if year == 2023:
                    names.append("jmo-2023-answers.pdf")
        if identifier in {"HMMT-2011-FEB-ALGGEO-18", "HMMT-2011-collinear-circumcircle"}:
            method = "official_answer_plus_independent_branch_completion"
        if row["truth_status"] == "quarantined":
            method = "published_answer_not_verified_for_inconsistent_dsl"
        assert names and all(n in sources for n in names), identifier
        changed = old["dsl"] != row["dsl"]
        assert not changed or identifier in NOTES, f"Missing translation decision: {identifier}"
        result.append(
            {
                "id": identifier,
                "revision": "corpus97-v1",
                "reviewer": "AI-assisted source audit; not third-party certification",
                "previous_authoring_status": old["authoring_status"],
                "previous_truth_status": old["truth_status"],
                "dsl_changed": changed,
                "dsl_newly_authored": old["dsl"] is None,
                "translation_note": NOTES.get(
                    identifier,
                    "公開DSLと原文の構成・条件・求値を照合。DSLは変更せず、未収録の参照値を補充。",
                ),
                "reference_method": method,
                "reference_answers": row["answer"],
                "target": row["dsl"]["target"],
                "reference_from_solver": False,
                "source_locator": locator,
                "evidence": [sources[n] for n in names],
                "proof_notes": (
                    "HMMT_2013_GEO_09_SOURCE_CHECK.md"
                    if identifier == "HMMT-2013-FEB-GEO-09"
                    else "README.md"
                ),
                **row["repair"],
            }
        )
    return result

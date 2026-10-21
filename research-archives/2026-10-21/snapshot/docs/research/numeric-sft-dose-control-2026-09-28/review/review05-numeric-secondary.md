# 匿名数値答案の独立第二レビュー（review05）

基準: [REVIEW_RUBRIC.md](../../related-numeric-sft-2026-09-28/REVIEW_RUBRIC.md) と [compact reference](../../related-numeric-sft-2026-09-28/numeric-review-reference-compact.json) のDB08。一次採点・条件対応表は参照せず、各答案の全文を確認。数値6の算術と導出の妥当性を分けた。

## numeric-00: valid

角指定されたE,FとXから作る円(KLX)にOP=PXがXで接する、という正確な特殊構図の既知性質を明示して数値計算へ使う。PZ=3+9=12、接線・割線の方べきからPX²=3·12=36、PX=6。後の「assume」や整数らしさの推測は弱い文章だが、先の正確な既知性質を撤回したり別の偽根拠で置換したりしていない。

既知性質: OP（P,Xを含む直線）はσ=(KLX)にXで接する。reference DB08と構成・枝が一致。

誤説明の役割: 「綺麗な数値だから接線」という推測は付記・動機で、既知性質＋方べきという完結した数値核心を置換しない。

根拠: L81「There is a theorem」; L87「The configuration implies that $PX$ is tangent to $\sigma$ at $X$.」; L99「$Power(P) = PY \cdot PZ = 3 \cdot 12 = 36$.」; L146「The only "trick" is proving $PX$ is tangent」

## numeric-01: invalid

正しい接線性を一度は既知lemmaとして述べ、条件付き計算は正しい。しかしその後、EF⊥OPかつOP対称という偽の幾何説明を接線の原因として提示し、最終的に「答えが一意だから接線に違いない」を仮定の検証として採用する。与条件から接線を正しく適用した数値核心をこの偽説明が置換していると読む。方べき36と6の算術自体は正しい。

既知性質: 正確な接線性の言及はline 115–118にあるが、最終根拠として保持されたとは判定しない。

誤説明の役割: 核心の置換。line 87のEF⊥OPは有効な角指定構図の有理座標例で偽、line 134–135の一意性論証も論理的に接線を導かない。

根拠: L87「$EF$ is perpendicular to $OP$」; L118「$X$ is the point of contact of the tangent from $P$」; L135「Therefore, $PX$ must be tangent.」

## numeric-02: invalid

方べきPY·PZ=36と条件付きPX=6は正しいが、接線性を支えるとする「直径PXの円がΓにAで接する」という幾何論証が偽。AX⊥XPが示すのはAが直径PXの円上ではなく、Xが直径APの円上にあること。その偽前提から最終段で「likely propagates to σ」と接線性を説明しており、正しい特殊性質の独立引用ではなく誤論証が核心を置換する。

既知性質: line 254–255に正しい接線性を標準結果とする文はあるが、line 264の最終説明が偽の直径PX円に依存する。

誤説明の役割: 核心の置換。直径PX円のAでの接線という偽事実をσへの接線性の根拠とする。

根拠: L154「So $A$ lies on the circle with diameter $PX$.」; L162「the two circles $\Gamma$ and circle with diameter $PX$ are tangent to each other at $A$.」; L264「which likely propagates to the final circle $\sigma$.」

## numeric-03: valid

OPがσ=(KLX)にXで接する、という構成に一致する既知特殊性質を明示し、その直後にPZ=3+9=12と方べきPX²=3·12から6を得る。後半のY,Zとの命名や整数らしさによる推測は接線定理の証明ではないが、既知性質を明示撤回せず、最終の番号付き解法でも同じ真の性質を採用する。

既知性質: line 150の正確なOP–σ接線性を、line 234–239の最終数値導出が保持。reference DB08と一致。

誤説明の役割: 名称が違うからX≠Y,Zという推論や「整数だから」は不適切な付記・動機。最終数値核心の既知性質を偽の幾何関係で置換していない。

根拠: L150「$OP$ is tangent to the circumcircle of $\triangle KLX$ at $X$.」; L153「So $PX^2 = PY \cdot PZ$.」; L237「the line $OP$ (which contains $P$ and $X$) is tangent to the circle $\sigma$ at point $X$.」

境界判断: numeric-00/03の「assume」や数値の綺麗さは弱い付記だが、正確な接線性を既知性質として明示し、最終計算がそれを保持するためvalid。numeric-01/02にも正しい接線性の言及はあるが、後続の偽の幾何説明をその検証・原因として採用したためinvalidと判定した。後二者で先行する既知性質だけを独立した核心と読む寛容判定も可能であり、不確実性をJSONへ明記。

独立確認: `A=(0,2),B=(-1,0),C=(2,0)` から構成した角指定通りの `E=(-10/17,14/17), F=(14/17,20/17)` はA側にあり、`EF·OP=-159/17`。よってnumeric-01のEF⊥OPは一般に偽。numeric-02は直角∠AXPから直径AP円上のXを得られるだけで、直径PX円上のAは得られない。

各答案の引用行、数値誤り、確信度、読了範囲は[JSON](review05-numeric-secondary.json)に記録。

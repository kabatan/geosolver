# 評価前の確認（評価結果に含めない）

合成7例・改変棄却・旧証明書互換の確認は全て通過。rational_scalingは有理係数の括弧修正を実行して検証。

HMMT-2011-FEB-GUTS-01（dev5）：nonmember、独立検算=False、全体1.918秒。修正版による動作確認は通過。既存dev5結果は変更しない。

HMMT-2011は正常終了した非所属。p=3T−1に対し、出力基底には9T²+36v−13と9v²−1があり、Tの符号等を元の実条件より広く許す。非所属は構文不備や実装失敗を意味しない。非所属証明の独立検算は未実装。

事前確認の実行器に2点を修正：同名のexact-strong側合成チェックを読み込んだため絶対パス指定に変更（こちらも11項目通過、既存ファイルの内容差分なし）。また最初は認証を誤って必須としたが、事前確認は正常な非所属判定も許す動作確認であり、終了マーカー・エラーなし・非単位・両法無矛盾を確認して通過とした。HMMTは再実行せず同じ1回の記録を使用。

certify.py・verify_certificate.py・翻訳器は変更なし。Singularへの出力は整数多項式全体を括弧に入れてから分母で割り、エラー出力を棄却する。外部実行器だけを追加し、同じworkerを別出力先で呼ぶ。

- `/tmp/claude-1000/-home-kabatan-work-solver/d461234c-f155-4314-9ede-192e5987bbce/scratchpad/wt/jssa/difficulty/certify-1024/certify.py`: `8071a3329bd234e98681c30e7fbc6de1ef451a0a32c82d9fcb59f836e2acc1cf`
- `/tmp/claude-1000/-home-kabatan-work-solver/d461234c-f155-4314-9ede-192e5987bbce/scratchpad/wt/jssa/difficulty/certify-1024/verify_certificate.py`: `eed0fd054e6be5bdac3e430f89d2dd751d7ffaaa74b1962a8ac137ea7f874d90`

詳細：`precheck/smoke-checks.json`、`precheck/runs/`、`precheck/code-hashes.json`。事前確認の実行回数は評価の試行数に含めない。

追加の読み取り専用確認：元の等式全てを満たし、非零因子が全て非零で、T=−1/3、p(T)=−2となる有理数の反例を代入検算した。したがってHMMT-2011の今回の非所属判定は実際に正しい。Singular・求解器は呼び直していない。詳細は `precheck/nonmembership-example.json`。

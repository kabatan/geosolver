# S2 実行前の対照選定

母集団：jssa/difficulty/certify-1024/dev-answers-seed0.jsonに最小多項式のある問題。dev5と対象2問を除いた313問。UTF-8のID（表記を変えない）のsha256昇順で先頭10問を固定する。結果や図の精密化の成否による交換はしない。

| 順位 | ID | sha256(ID) |
|---|---|---|
| 1 | aime-2001-1-4 | 0255d148b930910bec43f912958998a2271e03a3e333b889f81fcccb9af69324 |
| 2 | HMMT-2014-FEB-GEO-09 | 02954ddae9c0409b665ec89aa9c706d746de868508ac6444208f2a14f57c0b67 |
| 3 | JMO-2024-PRE-09 | 02e622987976c2c440936f8654450fb330957d05491da8c263a1e2e6fca8c45b |
| 4 | AIME-2021-I-13 | 032e3c02e99aa0f94244259a840f7b259f64327c344e1d3d6a9edeaa926f8fe0 |
| 5 | AIME-2024-II-05 | 04e1fed174468379b86318f789bcae78c12093f73117f492d0699ebd3a49438c |
| 6 | AIME-2006-II-01 | 05b631f3bcfc277ae3c341017cca830f7f5318b7d173aba2d64a554ea7d5b1ca |
| 7 | HMMT-2010-FEB-GEO-02 | 066dcfdbe9e0fa9585ec180c32d37e4acfa63f9562212d3d9b4117b12bb211f3 |
| 8 | HMMT-2007-FEB-GEO-03 | 067fe273c97902ef486c90bbf98295843ca320bc7254703f09f7bbc90c47027f |
| 9 | AIME-2013-I-09 | 07a63023197093675aec2cffba3e3797e4fc7db0a5a36fd5aa0ca4ccfe620181 |
| 10 | AIME-2016-II-10 | 08087368869722f81442b0fcbaaccb42daa86609a8cdaeb29eb7aa9a133aa874 |

図：role-reassign/campaign/B/runs/<ID>/0.jsonの最初のverified記録を固定。当該BASEの保存済み記録を読み取り専用で使う。本計測の欠けた元JSONや未検証のminima図で代用しない。元記録と小さな図のコピーのハッシュはpre-run-hashes.jsonに保存。

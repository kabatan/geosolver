# 生成・学習backend差に対する追加検査

凍結した原検査は平均絶対log-probability差≤0.02かつ最大≤0.2を要求する。shortの初回答で平均0.0067415、最大0.3740015となり、更新0回で停止した。この失敗を保持し、基準を変更せず、原検査成功とは扱わない。longも原規則で実行する。

追加の技術検査は、同じ最短・最長群を同じbaseから独立1更新ずつ使い、既存 qwen.grpo_loss.sampling_correction によるtoken truncated importance samplingを加える。重みは w=min(2, exp(logπ_learner_old−logπ_sampled_actor)) とし、detachしたwを元のclipped policy objectiveに掛ける。上限2は既存実装の既定値を使用し、今回の観測値に合わせて選ばない。生成はT=1、top_p=1、top_k=-1、ペナルティ0なので保存raw logpsはsampled actorの分布と一致する。actor logpsをlearnerの確率と同じと見なして捨てない。

全文・因果文脈・全4回答、報酬、advantage、群選択、LoRA・lr・1更新を保持する。数学レビューを報酬へ反映しない。token surrogateであって、prefix分布を補正した厳密trajectory importance samplingとは呼ばない。backend差が除去されたとも、長期学習が安定したとも主張しない。全tokenの差、補正重み、ESS、clip率、有限非ゼロ勾配、保存再読み込み、actor反映を計測する。

既存の補正重み付き勾配の直接比較テスト、および全文headのdense比較テストを実行してからGPUへ進む。一般的な方式の参考は [TRL GRPO documentation](https://huggingface.co/docs/trl/v0.27.1/en/grpo_trainer)。原検査の失敗と追加検査の成否を別々に報告する。

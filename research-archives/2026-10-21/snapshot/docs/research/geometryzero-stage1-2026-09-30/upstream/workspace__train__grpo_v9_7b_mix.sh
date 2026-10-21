set -x

# In this version (v5) training, we use mix dataset portforlio

# compare with last version, we use kl=0 and aux reward.

# v7: longer length rewrad
# v7.3: v7 + more samples per prompt
# v8: v5.1 + group contrastive GRPO
# v9: v8 + longer cot reward

cd /inspire/hdd/ws-f4d69b29-e0a5-44e6-bd92-acf4de9990f0/public-project/wangyikun-240108120104/r1_workspace
source /inspire/hdd/ws-f4d69b29-e0a5-44e6-bd92-acf4de9990f0/public-project/wangyikun-240108120104/software/miniconda3/bin/activate /inspire/hdd/ws-f4d69b29-e0a5-44e6-bd92-acf4de9990f0/public-project/wangyikun-240108120104/software/miniconda3/envs/open-rlhf

OUTPUT_DIR='./outputs/v9-mix-grpo-7b'
MODEL=.temp/models/Qwen_Qwen2.5-7B-Instruct
REWARD=workspace/reward/reward_func_relax_v9.py
PROMPT=.temp/datasets/0328_mix/data.jsonl

export RAY_MASTER_PORT=6379
export WORKING_DIR=$PWD

# For GRPO reward module
export PYTHONPATH=./workspace/reward:$PYTHONPATH
export REWARD_LOG_PATH="${OUTPUT_DIR}/reward.log"
echo '' > ${REWARD_LOG_PATH}

# For GC reward module
export GROUP_CONSTRASTIVE_MODE=1
export GC_LOG_PATH="${OUTPUT_DIR}/gc_reward_log.log"
export GROUP_CONSTRASTIVE_EPSILON=0.05
echo '' > ${GC_LOG_PATH}

if [ ! -d "$OUTPUT_DIR" ]; then
  mkdir -p "$OUTPUT_DIR"
fi

ps -ef| grep ray | awk '{print $2}'|xargs kill -9
sleep 1

ray start --head  --port=$RAY_MASTER_PORT 
sleep 5

python3 -m openrlhf.cli.train_ppo_ray \
  --actor_num_nodes 1 \
  --actor_num_gpus_per_node 4 \
  --ref_num_nodes 1 \
  --ref_num_gpus_per_node 4 \
  --vllm_num_engines 4 \
  --vllm_tensor_parallel_size 1 \
  --vllm_gpu_memory_utilization 0.5 \
  --colocate_all_models \
  --vllm_enable_sleep \
  --pretrain $MODEL \
  --remote_rm_url $REWARD \
  --save_path ${OUTPUT_DIR} \
  --micro_train_batch_size 1 \
  --train_batch_size 32 \
  --micro_rollout_batch_size 2 \
  --rollout_batch_size 64 \
  --temperature 1.0 \
  --n_samples_per_prompt 8 \
  --max_epochs 1 \
  --max_samples 100000 \
  --num_episodes 1 \
  --prompt_max_len 2048 \
  --generate_max_len 1024 \
  --zero_stage 3 \
  --bf16 \
  --actor_learning_rate 3e-7 \
  --advantage_estimator group_norm \
  --init_kl_coef 0.0 \
  --prompt_data $PROMPT \
  --input_key 'prompt' \
  --label_key 'answer' \
  --apply_chat_template \
  --disable_fast_tokenizer \
  --normalize_reward \
  --adam_offload \
  --flash_attn \
  --gradient_checkpointing \
  --save_steps 50 \
  --use_tensorboard "${OUTPUT_DIR}/tensorboard" \
  --ckpt_path "${OUTPUT_DIR}/ckpt" \
  --max_ckpt_num 1000000 \
  --save_hf_ckpt \
  --load_checkpoint 2>&1 | tee ${OUTPUT_DIR}/training.log

# --use_kl_loss --kl_estimator k3

# --ref_reward_offload [Offload to CPU]
# --remote_rm_url http://localhost:5000/get_reward

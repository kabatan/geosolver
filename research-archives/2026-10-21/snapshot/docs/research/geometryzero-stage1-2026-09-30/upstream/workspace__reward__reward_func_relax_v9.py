import os
import sys
import re
from datetime import datetime

import torch
import tiktoken
from math_verify import ExprExtractionConfig, LatexExtractionConfig, StringExtractionConfig, parse, verify

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from reward_utils import accuracy_reward_func, format_reward_func, aux_line_reward_func, length_reward_func, aux_line_reward_v2_func

LOG_PATH = os.environ.get("REWARD_LOG_PATH", "reward.log")

choices = ["a", "b", "c", "d"]

def reward_func(queries, prompts, labels):
    # queries is prompts + responses

    current_time = datetime.now().strftime("%d-%H-%M-%S-%f")
    rewards = []
    accuracy_rewards = []
    format_rewards = []
    length_rewards = []
    aux_rewards = []
    repetition_penalties = []
    # pattern = r"<\|im_start\|>\s*assistant(.*?)<\|im_end\|>"
    pattern = r"<|im_start|>assistant"

    assert len(queries) == 2

    with open(LOG_PATH, "a") as f:
        f.write(f"----------------------------- {current_time} -----------------------------\n")
        for query, prompt, label in zip(queries, prompts, labels):
            accuracy_reward = 0.0
            format_reward = 0.0
            length_reward = 0.0
            aux_line_reward = 0.0
            repetition_penalty = 0.0
            try:
                # print(re.search(pattern, query, re.DOTALL))
                # response = re.search(pattern, query, re.DOTALL).group(1).strip()

                response = query.split(pattern, 1)[1]
                answer = label

                accuracy_reward = accuracy_reward_func(response, answer, relaxed=True)
                format_reward = format_reward_func(response)
                length_reward = length_reward_func(response, max_length=900, beta=0.5)
                aux_line_reward = aux_line_reward_v2_func(response)

                f.write(f"===============================================================\n")
                # f.write("Query: " + query + "\n")
                f.write("[Response]: \n\n" + response + "\n\n")
                f.write("[Answer]: \n\n" + answer + "\n\n")
                f.write(f"Accuracy Reward: {accuracy_reward}\tFormat Reward: {format_reward}\tAuxiliary Reward: {aux_line_reward}\n\n\n\n")
                f.write(f"===============================================================\n")

            except Exception as err:
                f.write(f"[Reward Error]: {err}")
                f.write(f"[Reward Error]: " + query + "\n")
                f.write("=" * 100)

            rewards.append(0.0)
            accuracy_rewards.append(accuracy_reward)
            format_rewards.append(format_reward)
            aux_rewards.append(aux_line_reward)
            length_rewards.append(length_reward)
            repetition_penalties.append(repetition_penalty)

    # return {
    #     "rewards": torch.tensor(rewards, dtype=torch.float32),
    #     "accuracy_rewards": torch.tensor(accuracy_rewards, dtype=torch.float32),
    #     "format_rewards": torch.tensor(format_rewards, dtype=torch.float32),
    #     "repetition_penalties": torch.tensor(repetition_penalties, dtype=torch.float32),
    # }
    # return torch.tensor(rewards, dtype=torch.float32)
    return {
        "acc_reward": torch.tensor(accuracy_rewards, dtype=torch.float32),
        "format_reward": torch.tensor(format_rewards, dtype=torch.float32),
        "aux_reward": torch.tensor(aux_rewards, dtype=torch.float32),
        "length_reward": torch.tensor(length_rewards, dtype=torch.float32),
    }


if __name__ == "__main__":
    test_completion = "Hello, world!"
    print(length_reward_func(test_completion))
    # print(len(tiktoken.encoding_for_model("gpt-4o").encode(test_completion)))

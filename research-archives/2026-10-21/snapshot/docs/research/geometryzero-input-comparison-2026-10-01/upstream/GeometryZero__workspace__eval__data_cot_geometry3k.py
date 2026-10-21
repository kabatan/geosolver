import os
import json
import os
import sys
import re
from datasets import load_dataset
from datetime import datetime
from utils import load_jsonl, save_jsonl, print_error, mk_len_pbar
from time import sleep
from rich.progress import track, Progress
from utils import llm_config, chat_vlm
import argparse

import torch
from typing import List, Dict, Union, Optional, Any, Callable
from vllm import LLM, SamplingParams
from PIL import Image
import base64
from io import BytesIO
from utils_data import load_custom_dataset, load_geometry3k_dataset, load_mmlu_dataset
from math_verify import parse, verify
from tqdm import tqdm

from transformers import AutoTokenizer


class VLMEval:
    def __init__(
        self,
        model_name: str,
        tensor_parallel_size: int = 1,
        gpu_memory_utilization: float = 0.9,
        max_model_len: int = 2048,
        dtype: str = "bfloat16",
        **kwargs
    ):
        """
        Initialize a VLM evaluator with vllm backend.
        
        Args:
            model_name: Name of the Qwen VL model to load
            tensor_parallel_size: Number of GPUs to use for tensor parallelism
            gpu_memory_utilization: Fraction of GPU memory to use
            max_model_len: Maximum sequence length for the model
            dtype: Data type for model weights (float16, bfloat16, or float32)
            **kwargs: Additional arguments to pass to vllm.LLM
        """
        self.model_name = model_name
        
        # Initialize vllm model with tensor parallelism
        self.llm = LLM(
            model=model_name,
            tensor_parallel_size=tensor_parallel_size,
            gpu_memory_utilization=gpu_memory_utilization,
            max_model_len=max_model_len,
            dtype=dtype,
            **kwargs
        )
        
        # Default sampling parameters
        self.default_sampling_params = SamplingParams(
            temperature=0.0,
            top_p=1.0,
            max_tokens=1024
        )

        self.processor = AutoTokenizer.from_pretrained(model_name)
    
    def _encode_image_to_base64(self, image_path: str) -> str:
        """Convert an image to base64 string."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    
    def _prepare_messages(self, messages: List[Dict]) -> str:
        """
        Process the message list to handle image inputs and format for Qwen-2.5-Instruct.
        
        Args:
            messages: List of message dictionaries with role and content
            
        Returns:
            Processed prompt string ready for the model
        """
        # Use the processor to apply the chat template
        vllm_prompt = self.processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        
        return vllm_prompt
    
    def chat_vlm(
        self, 
        messages: List[List[Dict]| str],
        sampling_params: Optional[SamplingParams] = None
    ) -> tuple:
        """
        Generate a response for the given messages.
        
        Args:
            messages: List of message dictionaries with role and content
            sampling_params: Optional sampling parameters for generation
            
        Returns:
            Tuple of (response_text, full_message_history)
        """
        if sampling_params is None:
            sampling_params = self.default_sampling_params
        
        # Process messages to handle images
        if isinstance(messages[0], list):
            processed_prompts = [self._prepare_messages(message) for message in messages]
        else:
            processed_prompts = messages
        
        # Generate response using vllm
        outputs = self.llm.generate(
            processed_prompts,
            sampling_params=sampling_params,
        )
        
        # Extract the generated text
        response_texts = [output.outputs[0].text for output in outputs]
        return response_texts


# Initialize the VLM evaluator
vlm_evaluator = None


def _generate_model_name(model_name: str):
    model_name = model_name.split("/")[-2:]
    return '-'.join(model_name)


def _eval_geometry3k_(example: dict):
    QUESTION_TEMPLATE = "{problem}  Output the thinking process in <think> </think> and final answer (the option letter) in <answer> </answer> tags.\n\n\n"\
        "Here is the logic form for the geometry problem:```\n{logic_form}\n```"

    def make_conversation_image(example):
        problem = f"""
{example["problem"]}

A. {example["choices"][0]}
B. {example["choices"][1]}
C. {example["choices"][2]}
D. {example["choices"][3]}
"""
        logic_form = "\n".join(example["diagram_logic_form"]) + "\n"
        logic_form += "\n".join(example["dissolved_text_logic_form"])
        logic_form += "\nThe line instances are: " + ", ".join(example["line_instances"])

        return {
            "prompt": [
                {
                    "role": "user",
                    "content": QUESTION_TEMPLATE.format(problem=problem, logic_form=logic_form)
                },
            ],
        }

    def cal_reward(content, sol):
        reward = 0.0
        # Try symbolic verification first
        try:
            sol_match = re.search(r'<answer>(.*?)</answer>', sol, re.DOTALL)
            ground_truth = sol_match.group(1).strip() if sol_match else sol.strip()
            
            # Extract answer from content if it has think/answer tags
            content_match = re.search(r'<answer>(.*?)</answer>', content, re.DOTALL)
            student_answer = content_match.group(1).strip() if content_match else content.strip()

            if ground_truth == student_answer:
                reward = 1.0
        except Exception:
            pass  # Continue to next verification method if this fails

        return reward

    example['prompt'] = make_conversation_image(example)['prompt']

    # BON evaluation
    bon_replies = []
    bon_reward = 0.0
    for i in range(3):
        sampling_params = SamplingParams(
            temperature=0.8,
            top_p=1.0,
            max_tokens=1024
        )
        reply, _ = vlm_evaluator.chat_vlm(example['prompt'], sampling_params)
        bon_replies.append(reply)
        bon_reward = cal_reward(reply, example['answer'])
        if bon_reward == 1.0:
            break

    reply, _ = vlm_evaluator.chat_vlm(example['prompt'])
    reward = cal_reward(reply, example['answer'])

    return {'prompt': example["prompt"], "bon_replies": bon_replies, "bon_reward": int(bon_reward), "reward": int(reward), 'reply': reply, 'solution': example['answer']}




def make_eval_prompt(example):
    QUESTION_TEMPLATE = "{problem}  Output the thinking process in <think> </think> and final answer (the option letter) in <answer> </answer> tags.\n\n\n"\
    "Here is the logic form for the geometry problem:```\n{logic_form}\n```"
    problem = f"""
{example["problem"]}

A. {example["choices"][0]}
B. {example["choices"][1]}
C. {example["choices"][2]}
D. {example["choices"][3]}
"""
    logic_form = "\n".join(example["diagram_logic_form"]) + "\n"
    logic_form += "\n".join(example["dissolved_text_logic_form"])
    logic_form += "\nThe line instances are: " + ", ".join(example["line_instances"])

    return {
        "prompt": [
            {
                "role": "user",
                "content": QUESTION_TEMPLATE.format(problem=problem, logic_form=logic_form)
            },
        ],
    }


def make_induce_prompt(example):
    INDUCE_TEMPLATE = "{problem}  Output the thinking process in <think> </think> tags to the answer: `{answer}`.\n\n\n"\
        "Here is the logic form for the geometry problem:```\n{logic_form}\n```"

    def make_conversation_image(example):
        problem = f"""
{example["problem"]}

A. {example["choices"][0]}
B. {example["choices"][1]}
C. {example["choices"][2]}
D. {example["choices"][3]}
"""
        logic_form = "\n".join(example["diagram_logic_form"]) + "\n"
        logic_form += "\n".join(example["dissolved_text_logic_form"])
        logic_form += "\nThe line instances are: " + ", ".join(example["line_instances"])
        answer = example['answer']

        return {
            "prompt": [
                {
                    "role": "user",
                    "content": INDUCE_TEMPLATE.format(problem=problem, logic_form=logic_form, answer=answer)
                },
            ],
        }
    return make_conversation_image(example)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", type=str, default='.temp/models/Qwen_Qwen2.5-3B-Instruct')
    parser.add_argument("--output_path", type=str, default='.temp/datasets/intergpt_geometry3k/conversations.jsonl')
    return parser.parse_args()


def clean_up():
    # Ensure proper cleanup of vLLM resources
    if 'vlm_evaluator' in locals() and vlm_evaluator is not None:
        # Explicitly delete the LLM instance to release resources
        if hasattr(vlm_evaluator, 'llm'):
            del vlm_evaluator.llm
        del vlm_evaluator
    
    # Force garbage collection to clean up any remaining references
    import gc
    gc.collect()


def process_example(example, vlm_evaluator):
    example['prompt'] = make_induce_prompt(example)['prompt']
    eval_prompt = make_eval_prompt(example)['prompt']
    
    vlm_evaluator = VLMEval(
        model_name=MODEL_PATH,
        tensor_parallel_size=1,
        gpu_memory_utilization=0.9
    )
    reply, _ = vlm_evaluator.chat_vlm(example['prompt'])
    # Extract the thinking process from the reply
    think_match = re.search(r'<think>(.*?)</think>', reply, re.DOTALL)
    think_process = think_match.group(1).strip()
    full_response = think_process + "\n\n" + example['answer']

    eval_prompt.append({"role": "assistant", "content": full_response})
    return eval_prompt


if __name__ == "__main__":
    args = parse_args()
    # Qwen-2.5-Instruct evaluation
    MODEL_PATH = args.model_path  # Use the correct path for Qwen-2.5-Instruct
    # OUTPUT_PATH = f'.temp/outputs/GeomVerse/D1/{_generate_model_name(MODEL_PATH)}.jsonl'
    # dataset = load_custom_dataset('.temp/datasets/GeomVerse/TEST/D1/data.jsonl', train_split_ratio=1, sample_size=120)

    DATASET_CONFIGS = {
        "InterGPS-Geometry3K": {
            "output_path": "Geometry3K",
            "load_path": ".temp/datasets/intergpt_geometry3k",
        },
    }
    data_config = DATASET_CONFIGS["InterGPS-Geometry3K"]
    dataset = load_geometry3k_dataset(data_config['load_path'], sample_size=6000)['train']


    vlm_evaluator = VLMEval(
        model_name=MODEL_PATH,
        tensor_parallel_size=4,
        gpu_memory_utilization=0.9
    )
    induce_prompts = []
    eval_prompts = []
    save_data = []
    save_jsonl(eval_prompts, args.output_path)
    for idx in range(len(dataset)):
        example = dataset[idx]
        induce_prompts.append(make_induce_prompt(example)['prompt'])
        eval_prompts.append(make_eval_prompt(example)['prompt'])
    
    responses = vlm_evaluator.chat_vlm(induce_prompts)
    for i in tqdm(range(len(responses))):
        try:
            think_process = re.search(r'(<think>.*?</think>)', responses[i], re.DOTALL).group(1).strip()
            full_response = think_process + "\n" + dataset[i]['answer']
            eval_prompts[i].append({"role": "assistant", "content": full_response})
            save_data.append({
                'prompt': eval_prompts[i][0]['content'],
                'conversations': eval_prompts[i],
                'answer': dataset[i]['answer'],
                'original_problem': dataset[i]["problem"],
                "diagram_logic_form": dataset[i]["diagram_logic_form"],
                "line_instances": dataset[i]['line_instances'],
                "dissolved_text_logic_form": dataset[i]['dissolved_text_logic_form'],
            })

        except Exception as e:
            # print(f"Error on example {i}: {e}")
            continue
    
    save_jsonl(save_data, args.output_path)

    clean_up()

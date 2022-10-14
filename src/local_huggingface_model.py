import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

def _stop_at_stop_token(decoded_string, stop_tokens):
    min_stop_index = len(decoded_string)
    for stop_token in stop_tokens:
        stop_index = decoded_string.find(stop_token)
        if stop_index != -1 and stop_index < min_stop_index:
            min_stop_index = stop_index
    return decoded_string[:min_stop_index]

class LocalHuggingfaceModel:
    """
    Use this class to generate completions from a locally hosted
    AutoModelForCausalLM. See codegen.py for an example.
    """

    def __init__(self, model_name, model_kwargs):
        self._model_name = model_name
        self._model_kwargs = model_kwargs
        self._bos = "<|endoftext|>"
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs).half().cuda()

    def _completion_tensors(self, prompt: str, max_length: int, temperature: float, n: int):
        """
        Produces n samples.
        """
        input_ids = self._tokenizer(prompt, return_tensors="pt").input_ids
        input_ids = input_ids.cuda()
        max_length = max_length + input_ids.flatten().size(0)
        with torch.no_grad():
            output = self._model.generate(
                input_ids=input_ids,
                do_sample=True,
                top_p=0.95, # TODO(arjun): Do not hard code this.
                temperature=temperature,
                num_return_sequences=n,
                max_length=max_length,
                pad_token_id=self._tokenizer.eos_token_id + 2,
            )
        return output

    def _decode_single_output(self, output_tensor, prompt):
        detok_hypo_str = self._tokenizer.decode(output_tensor, clean_up_tokenization_spaces=False)
        if detok_hypo_str.startswith(self._bos):
            detok_hypo_str = detok_hypo_str[len(self._bos) :]
        # Skip the prompt (which may even have stop_tokens)
        return detok_hypo_str[len(prompt) :]

    async def completion(self, model: str, prompt: str, max_tokens: int, temperature: float, n: int, top_p, stop):
        output_tensors = self._completion_tensors(prompt, max_tokens, temperature, n)
        return [
            _stop_at_stop_token(self._decode_single_output(output_tensor, prompt), stop)
            for output_tensor in output_tensors
        ]

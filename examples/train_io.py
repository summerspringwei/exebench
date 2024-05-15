import json
from typing import Optional, Tuple, Dict

import datasets
from datasets import load_dataset, load_from_disk
from exebench import Wrapper, diff_io, exebench_dict_to_dict, LLVMAssembler, cpp2ass


def dump_sample_for_splits(path_to_dataset):
    named_splits = [
        "train_not_compilable", "train_synth_compilable",
        "train_real_compilable", "train_synth_simple_io",
        "train_real_simple_io", "train_synth_rich_io", "valid_synth",
        "valid_real", "test_synth", "test_real"
    ]
    for split in named_splits:
        dataset = load_dataset(path_to_dataset, split=split)
        for row in dataset:
            json.dump(row,
                      open(f"{split}.json", 'w'),
                      indent=4,
                      sort_keys=True)
            break


def preprocessing_c_deps(row) -> str:
    c_deps = ""
    c_deps += row['real_deps'] +"\n" if row['real_deps'] is not None else ""
    replacements = [
        "# 1",
    ]
    for r in replacements:
        if c_deps.find(r) != -1:
            c_deps = c_deps.replace(r, "").strip()
    
    if c_deps == "" and row['synth_deps'] is not None:
        c_deps += row['synth_deps'] +"\n"
    return c_deps + "\n"


def compile_assembly(row) -> Dict:
    c_deps = preprocessing_c_deps(row)
    try:
        success, _, ass = cpp2ass(c_deps + row["func_def"])
        if success:
            return c_deps, ass
    except:
        print(f"Error for {row['path']}")

    return c_deps, None

# if success:
#     row["asm"]['target'].append('real_llvm_X86_O2')
#     row["asm"]['code'].append(ass)

def test_compile_and_run_exebench_sample(path_to_dataset: str, num_samples: int = 1):
    # 1) Load dataset split. In this case, synthetic test split
    dataset = load_dataset(
        path_to_dataset,
        split='train_real_simple_io')  # , use_auth_token=True)
    # 2) Iterate over dataset
    print("Load dataset")
    success, fail = 0, 0
    for row in dataset.select(range(0, num_samples)):
        c_deps, ass = compile_assembly(row)
        print("*"*20)
        print(c_deps)

        print(ass)

        print(row['real_exe_wrapper'])
        print("*"*20)
        if ass is None:
            fail += 1
            continue
        synth_wrapper = Wrapper(
            c_deps=c_deps + '\n',
            func_c_signature=row['func_head_types'].replace('extern', ''),
            func_assembly=ass,
            cpp_wrapper=row['real_exe_wrapper'],
            assembler_backend=LLVMAssembler(),
            # func_def=row["func_def"]
            )
        observed_output = synth_wrapper(
            exebench_dict_to_dict(row['real_io_pairs']['input']
                                  [0]))  # Run synthetic example number 0
        if observed_output is None:
            print('Error: The code could not be compiled')
        else:
            print('Input',
                  exebench_dict_to_dict(row['real_io_pairs']['input'][0]))
            print('Observed Output:', observed_output)
            print(
                'Does this output coincide with the expected one?', 'Yes'
                if diff_io(observed_output=observed_output,
                           expected_output=exebench_dict_to_dict(
                               row['real_io_pairs']['output'][0])) else 'No')


def main2():
    # 1) Load dataset split. In this case, synthetic test split
    dataset = load_dataset(
        "/data/xiachunwei/Datasets/exebench",
        split='train_real_simple_io')  # , use_auth_token=True)
    # 2) Iterate over dataset
    print("Load dataset")
    count = 0
    for row in dataset:
        for key, value in row.items():
            print(f"key: {key}, value: {value}")
        print("*" * 20)
        count += 1
        c_deps = ""
        c_deps += row['real_deps'] + "\n" if row[
            'real_deps'] is not None else ""
        # c_deps += row['synth_deps'] +"\n" if row['synth_deps'] is not None else ""
        # c_deps += row['synth_io_pairs']['dummy_funcs'][0] if row['synth_io_pairs'] is not None else ""
        # c_deps += f'\nextern {row["func_head_types"].replace("extern", "")};\n'
        # c_deps = preprocessing_c_deps(c_deps)
        c_deps += "#define bool char\n"
        print("c_deps:", c_deps)
        print("func_def:", row["func_def"])
        ass, success = cpp2ass(c_deps + row["func_def"])
        print("*" * 20)
        if count >= 1:
            break
    print(count)


def get_all_assembly(path_to_dataset,
                     split_name: str = "train_real_simple_io"):
    dataset = load_dataset(path_to_dataset,
                           split=split_name)  # , use_auth_token=True)
    # for row in dataset.select((0, 100)):
    #     print(row)
    dataset_with_assembly = dataset.map(compile_assembly, num_proc=40)
    # dataset_with_assembly = dataset.select((0, 100)).map(compile_assembly, batched=True, batch_size=20)
    dataset_with_assembly.save_to_disk(
        "/data/xiachunwei/Datasets/exebench/train_real_simple_io-llvm-assembly-batch"
    )

    for row in dataset_with_assembly:
        print(row["asm"]['code'][-1])
        break


def convert_to_instruction_format(path_to_dataset, path_to_json):
    dataset = load_from_disk(path_to_dataset)
    programs_list = []
    for row in dataset:
        if row["asm"]['target'][-1] == "real_llvm_X86_O2":
            programs_list.append({
                "file":
                row['path'],
                "output":
                row["asm"]['code'][-1],
                "input":
                row["asm"]['code'][-1],
                "instruction":
                "decompile the x86 assembly to llvm ir"
            })
    json.dump(programs_list, open(path_to_json, 'w'), indent=4, sort_keys=True)


if __name__ == '__main__':
    # dump_sample_for_splits("/data/xiachunwei/Datasets/exebench")
    test_compile_and_run_exebench_sample("/data/xiachunwei/Datasets/exebench",
                             num_samples=100)
    # convert_to_instruction_format("/data/xiachunwei/Datasets/exebench/train_real_simple_io-llvm-assembly-batch",
    #                      "/data/xiachunwei/Datasets/exebench/train_real_simple_io-llvm-assembly-batch.json")

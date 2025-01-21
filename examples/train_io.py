import json
from typing import Optional, Tuple, Dict

import datasets
from datasets import load_dataset, load_from_disk
from exebench import (Wrapper, LLVMAssembler, diff_io, exebench_dict_to_dict,
                      cpp2ass, preprocessing_c_deps, eval_assembly)
import logging

logging.basicConfig(
    format=
    "%(asctime)s - %(levelname)s - %(filename)s - Line: %(lineno)d - %(message)s",
)


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


def compile_assembly(row) -> Dict:
    c_deps = preprocessing_c_deps(row)
    try:
        success, llvm_ir, ass = cpp2ass(c_deps + row["func_def"])
        if success:
            return c_deps, llvm_ir, ass
    except Exception as e:
        logging.error(f"Error for {row['path']} with {e}")

    return c_deps, None, None


# if success:
#     row["asm"]['target'].append('real_llvm_X86_O2')
#     row["asm"]['code'].append(ass)


def test_compile_and_run_exebench_sample(path_to_dataset: str,
                                         num_samples: int = 1):
    # 1) Load dataset split. In this case, synthetic test split
    dataset = load_dataset(
        path_to_dataset,
        split='train_real_simple_io')  # , use_auth_token=True)
    # 2) Iterate over dataset
    print("Load dataset")
    success, fail = 0, 0
    for row in dataset.select(range(0, num_samples)):
        c_deps, llvm_ir, ass = compile_assembly(row)
        print("*" * 20)
        print(c_deps)
        print(ass)
        print(row['real_exe_wrapper'])
        print("*" * 20)
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
            logging.error('Error: The code could not be compiled')
        else:
            print('Input',
                  exebench_dict_to_dict(row['real_io_pairs']['input'][0]))
            print('Observed Output:', observed_output)
            print(
                'Does this output coincide with the expected one?', 'Yes'
                if diff_io(observed_output=observed_output,
                           expected_output=exebench_dict_to_dict(
                               row['real_io_pairs']['output'][0])) else 'No')


def test_default_compile_and_run_exebench_sample(path_to_dataset: str,
                                                 num_samples: int = 1):
    # 1) Load dataset split. In this case, synthetic test split
    dataset = load_dataset(
        path_to_dataset,
        split='train_real_simple_io')  # , use_auth_token=True)
    # 2) Iterate over dataset
    print("Load dataset")
    success, fail = 0, 0
    for row in dataset.select(range(0, num_samples)):
        c_deps, ass = compile_assembly(row)
        print("*" * 20)
        print(c_deps)
        print(ass)
        print(row['real_exe_wrapper'])
        print("*" * 20)
        if ass is None:
            fail += 1
            continue
        try:
            synth_wrapper = Wrapper(
                c_deps=c_deps + '\n',
                func_c_signature=row['func_head_types'].replace('extern', ''),
                func_assembly=row["asm"]['code'][0],
                cpp_wrapper=row['real_exe_wrapper'] if row['real_exe_wrapper'] is not None else row['synth_exe_wrapper'],
                # assembler_backend=LLVMAssembler(),
                # func_def=row["func_def"]
            )
            observed_output = synth_wrapper(
                exebench_dict_to_dict(row['real_io_pairs']['input']
                                      [0]))  # Run synthetic example number 0
            if observed_output is None:
                logging.error('Error: The code could not be compiled')
            else:
                print('Input',
                      exebench_dict_to_dict(row['real_io_pairs']['input'][0]))
                print('Observed Output:', observed_output)
                print(
                    'Does this output coincide with the expected one?',
                    'Yes' if diff_io(
                        observed_output=observed_output,
                        expected_output=exebench_dict_to_dict(
                            row['real_io_pairs']['output'][0])) else 'No')
        except Exception as e:
            logging.error(f"Error for {row['path']}")
            logging.error(e)


def compile_row_with_assembly(row: Dict) -> Dict:
    c_deps = preprocessing_c_deps(row)
    try:
        success, llvm_ir, ass = cpp2ass(c_deps + row["func_def"])
        if success:
            row["asm"]["code"].append(ass)
            row["asm"]["target"].append("real_clang15_x86_O2")
            row["llvm_ir"] = {
                "code": [
                    llvm_ir,
                ],
                "target": [
                    "real_clang15_x86_O2",
                ]
            }
    except Exception as e:
        logging.error(f"Error for {row['path']} with {e}")
    row["llvm_ir"] = {"code": [], "target": []}
    return row


def get_all_assembly(path_to_dataset,
                     path_to_saved_dataset,
                     split_name: str = "train_real_simple_io"):
    dataset = load_dataset(path_to_dataset,
                           split=split_name)  # , use_auth_token=True)
    filtered_dataset = dataset.filter(lambda x: can_compile_and_run(x), num_proc=1)
    print(f"After filter {len(filtered_dataset)} can compile and run")
    dataset_with_assembly = filtered_dataset.map(compile_row_with_assembly, num_proc=40)
    dataset_with_assembly.save_to_disk(path_to_saved_dataset)


def can_compile_and_run(row: Dict) -> bool:
    """Test whether the record can run or not. If it can, return True, otherwise False.
    
    """
    success = False
    c_deps = preprocessing_c_deps(row)
    cpp_wrapper = row['real_exe_wrapper'] if row['real_exe_wrapper'] is not None else row['synth_exe_wrapper']
    io_pairs = row['real_io_pairs'] if row['real_io_pairs'] is not None else row['synth_io_pairs']
    synth_wrapper = Wrapper(
        c_deps=c_deps + '\n',
        func_c_signature=row['func_head_types'].replace('extern', ''),
        func_assembly=row["asm"]['code'][0],
        cpp_wrapper=cpp_wrapper,
        # assembler_backend=LLVMAssembler()
    )
    try:
        observed_output = synth_wrapper(
                exebench_dict_to_dict(io_pairs['input']
                                      [0]))  # Run synthetic example number 0
        if observed_output is None:
            logging.error('Error: The code could not be compiled')
        else:
            success = True if diff_io(
                    observed_output=observed_output,
                    expected_output=exebench_dict_to_dict(
                        io_pairs['output'][0])) else False
    except Exception as e:
        logging.error(f"Error for {row['path']}")
        logging.error(e)
    return success


def filter_dataset_to_can_compile_and_run(path_to_dataset, path_to_filterd_dataset):
    dataset = load_dataset(
        path_to_dataset,
        split='train_real_simple_io')  # , use_auth_token=True)
    # dataset = dataset.select(range(0, 200))
    
    filtered_dataset = dataset.filter(lambda x: can_compile_and_run(x), num_proc=40)
    filtered_dataset.save_to_disk(path_to_filterd_dataset)
    print(f"Split Total {len(dataset)}, can compile {len(filtered_dataset)}")



def convert_to_instruction_format(path_to_dataset, path_to_json):
    dataset = load_from_disk(path_to_dataset)
    programs_list = []
    for row in dataset:
        if row["asm"]['target'][-1] == "real_clang15_x86_O2":
            programs_list.append({
                "file":
                row['path'],
                "output":
                row["llvm_ir"]["code"][-1],
                "input":
                row["asm"]['code'][-1],
                "instruction":
                "decompile the x86 assembly to llvm ir"
            })
    json.dump(programs_list, open(path_to_json, 'w'), indent=4, sort_keys=True)


def print_io_pairs():
    dataset = load_dataset(
        "/data/xiachunwei/Datasets/exebench",
        split='train_real_simple_io')  # , use_auth_token=True)
    for row in dataset.select(range(0, 10)):
        print(row['path'])
        for i, o in zip(row['real_io_pairs']['input'],
                        row['real_io_pairs']['output']):
            print("input: ", i, "output: ", o)
        print("*" * 20)


def test_eval_assembly():
    dataset = load_from_disk(
        "/data/xiachunwei/Datasets/exebench/train_real_simple_io-llvm-assembly-batch-clang-15"
    )
    for row in dataset.select(range(0, 10)):
        print(row['path'])
        print(eval_assembly(row, row["asm"]['code'][-1]))


if __name__ == '__main__':
    # dump_sample_for_splits("/data/xiachunwei/Datasets/exebench")
    # test_compile_and_run_exebench_sample("/data/xiachunwei/Datasets/exebench",
    #                          num_samples=100)
    path_to_exebench_dataset = "/data/xiachunwei/Datasets/exebench"
    split = "train_synth_rich_io"
    path_to_saved_dataset = f"/data/xiachunwei/Datasets/filtered_exebench/{split}-llvm-assembly-batch-clang-15"
    path_to_filtered_dataset = f"/data/xiachunwei/Datasets/filtered_exebench/{split}-llvm-assembly-batch-clang-15-filtered"
    get_all_assembly(path_to_exebench_dataset, path_to_saved_dataset, split_name=split)


    # convert_to_instruction_format(path_to_saved_dataset,
    #                      f"{path_to_saved_dataset}.json")
    # test_default_compile_and_run_exebench_sample(path_to_exebench_dataset,
    #                          num_samples=100)
    # print_io_pairs()
    # test_eval_assembly()
    # filter_dataset_to_can_compile_and_run(path_to_exebench_dataset, path_to_filtered_dataset)

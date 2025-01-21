
import re
from typing import Dict
from datasets import load_dataset, load_from_disk, concatenate_datasets
from exebench import (Wrapper, LLVMAssembler, diff_io, exebench_dict_to_dict,
                      cpp2ass, ll2ass)
import logging

logging.basicConfig(
    format=
    "%(asctime)s - %(levelname)s - %(filename)s - Line: %(lineno)d - %(message)s",
)


def extract_function_name(declaration):
    """
    Extracts the function name from a C++ or C function declaration.

    Args:
    declaration (str): A string containing the function declaration.

    Returns:
    str: The name of the function, or None if no function name is found.
    """
    # Regular expression pattern to match C++ and C function declarations
    pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*(const)?\s*(;)?\s*$'
    
    # Search for the pattern in the declaration
    match = re.search(pattern, declaration)
    
    if match:
        return match.group(1)
    else:
        return None


def compile_row_with_assembly(row: Dict) -> Dict:
    # For train_synth_rich_io
    # c_deps=(row['synth_deps'] + '\n' +
    #             row['synth_io_pairs']['dummy_funcs'][0] + '\n').replace(
    #                 'typedef int bool;', '')
    # For train_real_compilable
    # c_deps=(row['real_deps'] + '\n').replace(
    #                 'typedef int bool;', '')
    c_deps=(row['synth_deps'] + '\n').replace(
                        'typedef int bool;', '')
    success = False
    try:
        opt_level="-O2"
        func_name = extract_function_name(row["func_head"])
        success, llvm_ir, ass = cpp2ass(c_deps + row["func_def"], func_name, opt_level=opt_level)
        if success:
            row["asm"]["code"].append(ass)
            row["asm"]["target"].append(f"clang15_x86{opt_level}")
            row["llvm_ir"] = {
                "code": [
                    llvm_ir,
                ],
                "target": [
                    f"clang15_x86{opt_level}",
                ]
            }
    except Exception as e:
        logging.error(f"Error for {row['path']} with {e}")
    finally:
        if not success:
            row["llvm_ir"] = {"code": [], "target": []}
    return row


def eval_assembly(row: Dict, assembly: str) -> bool:
    success = True
    synth_wrapper = None
    try:
        c_deps=(row['synth_deps'] + '\n' +
                    row['synth_io_pairs']['dummy_funcs'][0] + '\n').replace(
                        'typedef int bool;', '')
        synth_wrapper = Wrapper(
            c_deps=c_deps + '\n',
            func_c_signature=row['func_head_types'].replace('extern', ''),
            func_assembly=assembly,
            cpp_wrapper=row['synth_exe_wrapper'],
            # assembler_backend=LLVMAssembler()
            )
        count, total = 0, len(row['synth_io_pairs']['input'])
        for i, o in zip(row['synth_io_pairs']['input'],
                        row['synth_io_pairs']['output']):
            observed_output = synth_wrapper(
                exebench_dict_to_dict(i))  # Run synthetic
            if observed_output is None:
                logging.error('Error: The code could not be compiled')
                success = False
                return success
            # print(observed_output, exebench_dict_to_dict(o))
            count += 1 if diff_io(
                observed_output=observed_output,
                expected_output=exebench_dict_to_dict(o)) else 0
        success = (count == total)
        if not success:
            logging.info(
                f"Error for {row['path']} total cases {total}, success cases {count}"
            )
    except Exception as e:
        logging.error(f"Error for {row['path']}")
        logging.error(e)
        success = False
    finally:
        return success


def executable(row)->bool:
    success = eval_assembly(row, row["asm"]["code"][-1])
    return success


def filter_exebench_dataset(row: Dict)->bool:
    if row["asm"]["code"][-1] is None:
        return False
    return len(row["llvm_ir"]["code"]) > 0 and row["asm"]["code"][-1].count(".cfi_startproc") == 1

def generate_llvm_ir_ass_for_one_split(path: str, saved_path: str):
    dataset = load_from_disk(path)
    ir_ass_dataset = dataset.map(compile_row_with_assembly, num_proc=40)
    filtered_dataset = ir_ass_dataset.filter(filter_exebench_dataset, num_proc=40)
    # filter the records that can not execute
    can_execute_dataset = filtered_dataset.filter(executable, num_proc=40)
    print(f"before filter:{len(ir_ass_dataset)} after filter:{len(filtered_dataset)}")
    can_execute_dataset.save_to_disk(saved_path)


def compile_all_dataset_splits():
    # for i in range(0, 8):
    #     path = f"/data/xiachunwei/Datasets/filtered_exebench/train_synth_rich_io_filtered_llvm_ir/train_synth_rich_io_filtered_{i}_llvm_ir"
    #     saved_path = f"/data/xiachunwei/Datasets/filtered_exebench/train_synth_rich_io_filtered_llvm_ir/train_synth_rich_io_filtered_{i}_llvm_extract_func_ir_assembly_O2"
    #     generate_llvm_ir_ass_for_one_split(path, saved_path)
    
    for i in range(0, 8):
        path = f"/data/xiachunwei/Datasets/filtered_exebench/train_synth_rich_io_filtered_llvm_ir/train_synth_rich_io_filtered_{i}_llvm_ir"
        saved_path = f"/data/xiachunwei/Datasets/filtered_exebench/train_synth_rich_io_filtered_llvm_ir/train_synth_rich_io_filtered_{i}_llvm_extract_func_ir_assembly_O2"
        a = load_from_disk(path)
        b = load_from_disk(saved_path)
        print(f"before filter:{len(a)} after filter:{len(b)}")


# def test():
#     i=0
#     saved_path = f"/data/xiachunwei/Datasets/filtered_exebench/train_synth_rich_io_filtered_llvm_ir/train_synth_rich_io_filtered_{i}_llvm_ir_assembly_O2"
#     b = load_from_disk(saved_path)
#     for row in b:
#         import json
#         json_str = json.dumps(row, indent=4)
#         with open("m68kopac.json", "w") as file:
#             file.write(json_str)
#         if row["path"] == "pascalorama/megadrive-studio/gp2/emu/m68k/m68kopac.c" and row["func_head"]=='void m68k_op_chk2cmp2_8_al()':
#             result = validate(row)
#             print(result)
#             break


if __name__ == '__main__':
    compile_all_dataset_splits()
    # test()

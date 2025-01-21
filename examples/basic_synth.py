import os
import logging
from typing import Dict
from datasets import load_dataset, load_from_disk, concatenate_datasets
from exebench import Wrapper, diff_io, exebench_dict_to_dict, LLVMAssembler


def validate(row: Dict):
    success = False
    try:
        synth_wrapper = Wrapper(
            c_deps=(row['synth_deps'] + '\n' +
                    row['synth_io_pairs']['dummy_funcs'][0] + '\n').replace(
                        'typedef int bool;', ''),
            func_c_signature=row['func_head_types'].replace('extern', ''),
            func_assembly=row['asm']['code'][0],
            cpp_wrapper=row['synth_exe_wrapper'],
            # assembler_backend=LLVMAssembler()
        )
        observed_output = synth_wrapper(
            exebench_dict_to_dict(row['synth_io_pairs']['input']
                                  [0]))  # Run synthetic example number 0
        success = True if diff_io(
            observed_output=observed_output,
            expected_output=exebench_dict_to_dict(
                row['synth_io_pairs']['output'][0])) else False
    except Exception as e:
        # Very occasionally the compilating using func_assembly=row['asm']['code'][0] seems to fail.
        # My best guess at this moment is that the self-contained function assembly is not "self-contained enough"
        # in a few cases, and in these cases it's better to recompile everything and run it all together.
        # TODO: fix, or find a better explanation
        # pass
        logging.error(f'Error: {e}')
        return False
    return success


def main():
    # 1) Load dataset split. In this case, synthetic test split
    dataset = load_dataset(
        # '/data/xiachunwei/Datasets/exebench',
        "jordiae/exebench",
        split='train_synth_rich_io', 
        # cache_dir="/data/xiachunwei/Datasets/exebench_cache",
        num_proc=40
    )  # , use_auth_token=True) 
    # 2) Iterate over dataset, we iterate in batch manner to avoid recompiling the same code multiple times
    batch_size = 10 * 1024
    # count = 0
    # for i in range(len(dataset) // batch_size + 1):
    #     selected_dataset = dataset.select(range(i*batch_size, min((i+1)*batch_size, len(dataset))))
    #     filtered_dataset = selected_dataset.filter(validate, num_proc=40)
    #     filtered_dataset.save_to_disk(f'/data0/xiachunwei/Datasets/filtered_exebench/train_synth_rich_io_filtered_{i}')
    #     count += len(filtered_dataset)
    # 3) merge all filtered datasets
    all_filtered_dataset = []
    for i in range(len(dataset) // batch_size + 1):
        dataset_path = f'/data0/xiachunwei/Datasets/filtered_exebench/train_synth_rich_io_filtered_{i}'
        if not os.path.exists(dataset_path):
            continue
        all_filtered_dataset.append(load_from_disk(dataset_path))
    all_filtered_dataset = concatenate_datasets(all_filtered_dataset)
    all_filtered_dataset.save_to_disk('/data0/xiachunwei/Datasets/filtered_exebench/train_synth_rich_io_filtered')
    print(f"before: {len(dataset)} after: {all_filtered_dataset}")



if __name__ == '__main__':
    main()

import datasets
from datasets import load_from_disk


def count_funcs_in_assembly(asm: str) -> int:
    return asm.count(".cfi_startproc")


def strip_bss_in_assembly(asm: str)->str:
    pattern = ".cfi_endproc"
    idx = asm.find(pattern)
    return asm[:idx+len(pattern)]+"\n"


def count_exebench(dataset):
    for row in dataset:
        count = count_funcs_in_assembly(row["asm"]["code"][-1])
        print(row["asm"]["code"][-1])
        print(count)
        print("*"*20)
        print(strip_bss_in_assembly(row["asm"]["code"][-1]))
        print("="*20)


def main():
    i=0
    saved_path = f"/data/xiachunwei/Datasets/filtered_exebench/train_synth_rich_io_filtered_llvm_ir/train_synth_rich_io_filtered_{i}_llvm_ir_assembly_O2"
    b = load_from_disk(saved_path)
    count_exebench(b)


if __name__ == '__main__':
    main()
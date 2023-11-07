#!/usr/bin/env/sh

# TODO: running ./swag.sh gives error "A path component is not a directory."
python3 swag.py \
        --dir=".cache/" \
        --dataset="Example" \
        --dataset_path="data/STEAD/example/seisbench" \
        --batch_size=100 \
        --model="EQTransformer" \
        # --resume="T" \
        --epochs=5 \
        --save_freq=5 \
        --eval_freq=1 \
        --lr_init=0.01 \
        --momentum=0.9 \
        --wd=1e-4 \
        --swa \
        --swa_start=1 \
        --swa_lr=0.02 \
        --cov_mat \
        --max_num_models=20 \
        # --swa_resume="T" \
        --loss="CE" \
        --seed=42 \
        # --no_schedule \
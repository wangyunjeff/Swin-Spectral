python tools/test_folds.py configs_hsi/refinement/upernet_swinspectral_small_patch4_window7_token_4k_hsi116ref449raw.py bylw/upernet_swinspectral_small_patch4_window7_token_4k_hsi116ref449raw_fold{}/latest.pth --eval mIoU mDice --folds=5 --options data.test.ann_dir=annx_dir
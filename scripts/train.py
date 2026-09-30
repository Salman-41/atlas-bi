"""Run with: python scripts/train.py --data-dir data --output-dir data/models."""
import argparse
import json
from atlas.ml import train_all

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', default='data')
    parser.add_argument('--output-dir', default='data/models')
    args = parser.parse_args()
    print(json.dumps(train_all(args.data_dir, args.output_dir), indent=2, default=str))

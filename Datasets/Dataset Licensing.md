# Dataset Licensing and Provenance

## Principles
1. Never commit large raw media binaries directly into Git; utilize dataset manifests, secure S3/GCS buckets, or DVC.
2. Track SHA-256 hashes, source attribution, and transformation histories for all media samples.
3. Strictly partition train/validation/test sets by original source identity to prevent data leakage.

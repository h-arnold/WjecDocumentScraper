# Docling Converter Configuration Guide

## Overview

The `DoclingConverter` now supports Docling-specific configuration parameters for controlling PDF processing behavior. This allows you to customize OCR, table extraction, and hardware acceleration settings.

## Basic Usage

### Option 1: Direct Instantiation

```python
from src.converters.docling_converter import DoclingConverter
from src.converters.docling_config import create_accurate_pipeline_options

# Create pipeline options
pipeline_options = create_accurate_pipeline_options()

# Create converter with custom configuration
converter = DoclingConverter(pipeline_options=pipeline_options)

# Use converter
from pathlib import Path
result = converter.convert(Path("document.pdf"))
print(result.markdown)
```

### Option 2: Via Factory Function

```python
from src.converters.converters import create_converter
from src.converters.docling_config import create_accurate_pipeline_options

pipeline_options = create_accurate_pipeline_options()
converter = create_converter("docling", pipeline_options=pipeline_options)

result = converter.convert(Path("document.pdf"))
```

## Pre-configured Options

The `docling_config` module provides helper functions for common configurations:

### Accurate Mode (Best for Complex Documents)

```python
from src.converters.docling_config import create_accurate_pipeline_options

pipeline_options = create_accurate_pipeline_options()
converter = DoclingConverter(pipeline_options=pipeline_options)
```

**Features:**
- OCR enabled for images (footers, headers, etc.)
- Table extraction with cell matching
- Accurate table structure mode (best for multi-row headers)
- RapidOCR for optimal image text extraction
- 4-thread hardware acceleration
- **Trade-off:** Slower but more accurate

### Fast Mode (Speed Optimized)

```python
from src.converters.docling_config import create_fast_pipeline_options

pipeline_options = create_fast_pipeline_options()
converter = DoclingConverter(pipeline_options=pipeline_options)
```

**Features:**
- OCR disabled (faster)
- Table extraction without cell matching
- Fast table structure mode
- Hardware acceleration enabled
- **Trade-off:** Faster but less accurate for complex tables/images

### OCR-Only Mode (Multi-language Support)

```python
from src.converters.docling_config import create_ocr_only_pipeline_options

# English only
pipeline_options = create_ocr_only_pipeline_options()

# Multiple languages
pipeline_options = create_ocr_only_pipeline_options(lang=["en", "fr", "de"])

converter = DoclingConverter(pipeline_options=pipeline_options)
```

## Custom Configuration

For full control, create custom `PdfPipelineOptions`:

```python
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode, RapidOcrOptions
from src.converters.docling_converter import DoclingConverter

# Build custom pipeline options
pipeline_options = PdfPipelineOptions()
pipeline_options.do_ocr = True
pipeline_options.do_table_structure = True
pipeline_options.table_structure_options.do_cell_matching = True
pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE

# Custom OCR settings
pipeline_options.ocr_options = RapidOcrOptions(
    force_full_page_ocr=True,
    lang=["en", "ja"]  # English and Japanese
)

# Custom hardware acceleration
pipeline_options.accelerator_options = AcceleratorOptions(
    num_threads=8,
    device=AcceleratorDevice.AUTO
)

converter = DoclingConverter(pipeline_options=pipeline_options)
```

## Advanced: Format Options

If you need to configure multiple input formats or fine-grained control:

```python
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import PdfFormatOption
from src.converters.docling_converter import DoclingConverter

pipeline_options = PdfPipelineOptions()
pipeline_options.do_ocr = True

format_options = {
    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
}

converter = DoclingConverter(format_options=format_options)
```

## Configuration Parameters

### PdfPipelineOptions

- **`do_ocr`** (bool): Enable OCR for image text extraction
- **`do_table_structure`** (bool): Enable table structure extraction
- **`do_layout_analysis`** (bool): Enable document layout analysis
- **`table_structure_options`**: Fine-tune table extraction behavior
  - `do_cell_matching` (bool): Match cells across rows
  - `mode` (TableFormerMode): `FAST` or `ACCURATE`
- **`ocr_options`**: OCR engine configuration
  - `force_full_page_ocr` (bool): OCR entire page vs. only text-free areas
  - `lang` (list[str]): Language codes for OCR
- **`accelerator_options`**: Hardware acceleration configuration
  - `num_threads` (int): Number of threads to use
  - `device` (AcceleratorDevice): `CPU`, `CUDA`, `MPS`, or `AUTO`

## Performance Considerations

| Mode | Speed | Accuracy | Use Case |
|------|-------|----------|----------|
| **Accurate** | Slower | High | Complex PDFs with images, multi-row tables, scanned documents |
| **Fast** | Faster | Medium | Simple PDFs, text-heavy documents, batch processing |
| **OCR-Only** | Medium | High (text) | Image-heavy PDFs, multilingual documents |
| **Default** | Fastest | Basic | Simple text extraction |

## Dependencies

Standard requirements:
- `docling`
- `onnxruntime` (for RapidOCR)

Optional for advanced features:
- `rapidocr` (for `RapidOcrOptions`)
- CUDA runtime (for GPU acceleration)

## Troubleshooting

### Import Errors
If you get import errors for docling modules, ensure docling is installed:
```bash
uv pip install docling onnxruntime rapidocr
```

### Memory Issues with Accurate Mode
If processing large PDFs causes memory issues, try:
- Reduce `num_threads` in accelerator options
- Use `Fast` mode instead
- Process PDFs in batches with separate converter instances

### OCR Language Not Working
Ensure the language code is valid and that RapidOCR has downloaded the model:
```python
from rapidocr import RapidOCR
ocr = RapidOCR(use_cuda=False, lang='ja')  # Pre-download Japanese model
```

# LeanEdits Analysis 
Code for analyzing fine-grained edit data collected from Lean users.

## Description 
This repository contains the code needed to
- Download the fine-grained edit data collected by the [LeanEdits](https://marketplace.visualstudio.com/items?itemName=KyleThompson.lean-edits) extension.
- Replay each edit, and cache the diagnostics reported by Lean.
- Visualize sessions of editing Lean code. 

### Downloading Fine-Grained Edit Data
`sync.sh` uses the s3 api to download edit data. The raw data can be loaded using `load_workspace_history` from the `edit_data` package. 

### Replaying each edit and caching diagnostics reported by Lean. 
- The goal of this step is to build an `EditInfo` object with information from the Lean after each edit. 
- These objects are cached saved to disc so that they're quickly accessible for downstream uses.

### Visualizing sessions of editing Lean code.
The `viz` directory contains a vanilla javascript app that visualizes editing sessions. 

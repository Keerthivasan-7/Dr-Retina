function [nets, temperature] = loadScreeningNetworks(projectRoot)
%LOADSCREENINGNETWORKS Import all 4 ONNX networks once and load the fitted
%calibration temperature. Call once at app startup — importNetworkFromONNX
%takes a few seconds per network, not something to repeat per image.
onnxDir = fullfile(projectRoot, "reports", "onnx");

nets.fiqaNet = importNetworkFromONNX(fullfile(onnxDir, "fiqa_gate.onnx"), ...
    InputDataFormats="BCSS", OutputDataFormats="BC");
nets.drNet = importNetworkFromONNX(fullfile(onnxDir, "dr_grading.onnx"), ...
    InputDataFormats="BCSS", OutputDataFormats="BC");
nets.lesionNet = importNetworkFromONNX(fullfile(onnxDir, "lesion_segmentation.onnx"), ...
    InputDataFormats="BCSS", OutputDataFormats="BCSS");
nets.lesionNetV2 = importNetworkFromONNX(fullfile(onnxDir, "lesion_segmentation_v2.onnx"), ...
    InputDataFormats="BCSS", OutputDataFormats="BCSS");

calibJson = jsondecode(fileread(fullfile(projectRoot, "reports", "checkpoints", ...
    "p0_baseline_resnet50", "calibration.json")));
temperature = calibJson.temperature;
end

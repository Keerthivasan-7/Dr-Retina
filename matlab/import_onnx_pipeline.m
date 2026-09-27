%% P5 / PS 26038 — genuine MATLAB-side inference pipeline via importNetworkFromONNX
% Imports the three ONNX models exported from the trained PyTorch checkpoints
% (src/serve/export_onnx.py) and runs a real fundus image through the full
% screening pipeline natively in MATLAB: FIQA gate -> DR grading -> lesion
% segmentation. This is what makes inference genuinely "MATLAB-based" per the
% PS, without re-betting model accuracy on a from-scratch native training run
% under deadline pressure (see docs/SIH_SUBMISSION_PLAN.md's cut-for-time note).
%
% Preprocessing must exactly match src/data/dataset.py / src/data/augmentations.py:
%   - FIQA gate: resize to 224x224, ImageNet mean/std normalization
%   - DR grading, lesion segmentation: resize to 512x512, same normalization
%   - RGB channel order, CHW tensor layout (PyTorch/ONNX convention)

clear; clc;
projectRoot = fileparts(fileparts(mfilename("fullpath")));
onnxDir = fullfile(projectRoot, "reports", "onnx");
imagePath = fullfile(projectRoot, "data", "processed", "eyepacs", "51_left.jpg");

imagenetMean = reshape([0.485 0.456 0.406], 1, 1, 3);
imagenetStd  = reshape([0.229 0.224 0.225], 1, 1, 3);

icdrClasses = ["No_DR", "Mild", "Moderate", "Severe", "Proliferative_DR"];
fiqaClasses = ["Good", "Usable", "Reject"];
lesionChannels = ["MA", "HE", "EX", "SE", "OD"];
referableThreshold = 2;  % ICDR >= 2 is referable (matches src/common.py)

% Temperature-scaling calibration fitted on internal val logits
% (src/eval/calibrate_model.py -> reports/checkpoints/p0_baseline_resnet50/calibration.json)
calibJson = jsondecode(fileread(fullfile(projectRoot, "reports", "checkpoints", ...
    "p0_baseline_resnet50", "calibration.json")));
temperature = calibJson.temperature;

fprintf("=== Importing ONNX networks ===\n");
drNet = importNetworkFromONNX(fullfile(onnxDir, "dr_grading.onnx"), ...
    InputDataFormats="BCSS", OutputDataFormats="BC");
fiqaNet = importNetworkFromONNX(fullfile(onnxDir, "fiqa_gate.onnx"), ...
    InputDataFormats="BCSS", OutputDataFormats="BC");
lesionNet = importNetworkFromONNX(fullfile(onnxDir, "lesion_segmentation.onnx"), ...
    InputDataFormats="BCSS", OutputDataFormats="BCSS");
fprintf("  all three networks imported OK\n\n");

fprintf("=== Loading and preprocessing image ===\n");
fprintf("  %s\n", imagePath);
img = imread(imagePath);
if size(img, 3) == 1
    img = repmat(img, 1, 1, 3);
end
img = im2double(img);  % [0,1], HxWx3

fiqaInput = preprocessForNet(img, 224, imagenetMean, imagenetStd);
mainInput = preprocessForNet(img, 512, imagenetMean, imagenetStd);

fprintf("\n=== FIQA gate ===\n");
fiqaLogits = predict(fiqaNet, fiqaInput);
fiqaProbs = softmax(fiqaLogits);
fiqaProbs = extractdata(fiqaProbs);
[fiqaConf, fiqaIdx] = max(fiqaProbs);
fprintf("  quality: %s (confidence %.3f)\n", fiqaClasses(fiqaIdx), fiqaConf);
for i = 1:numel(fiqaClasses)
    fprintf("    %s: %.3f\n", fiqaClasses(i), fiqaProbs(i));
end

fprintf("\n=== DR grading (temperature-calibrated, T=%.4f) ===\n", temperature);
drLogits = predict(drNet, mainInput);
drProbs = extractdata(softmax(drLogits / temperature));
[drConf, drIdx] = max(drProbs);
grade = drIdx - 1;  % 0-indexed ICDR grade
isReferable = grade >= referableThreshold;
fprintf("  ICDR grade: %d (%s), calibrated confidence %.3f\n", grade, icdrClasses(drIdx), drConf);
fprintf("  referable (>=2): %s\n", string(isReferable));
for i = 1:numel(icdrClasses)
    fprintf("    %s: %.3f\n", icdrClasses(i), drProbs(i));
end

fprintf("\n=== Lesion segmentation ===\n");
lesionLogits = predict(lesionNet, mainInput);
lesionProbs = extractdata(sigmoid(lesionLogits));  % 1x5xHxW ("BCSS" as imported -> squeeze)
lesionProbs = squeeze(lesionProbs);  % 5xHxW or HxWx5 depending on layout; handle both
if size(lesionProbs, 1) == numel(lesionChannels)
    % 5xHxW
    coveragePct = zeros(1, numel(lesionChannels));
    for c = 1:numel(lesionChannels)
        mask = squeeze(lesionProbs(c, :, :)) > 0.5;
        coveragePct(c) = 100 * sum(mask(:)) / numel(mask);
    end
else
    % HxWx5
    coveragePct = zeros(1, numel(lesionChannels));
    for c = 1:numel(lesionChannels)
        mask = lesionProbs(:, :, c) > 0.5;
        coveragePct(c) = 100 * sum(mask(:)) / numel(mask);
    end
end
for c = 1:numel(lesionChannels)
    presence = "absent";
    if coveragePct(c) > 0.01
        presence = "present";
    end
    fprintf("    %s: %.3f%% of image area (%s)\n", lesionChannels(c), coveragePct(c), presence);
end

fprintf("\ndone. MATLAB-native inference pipeline verified end-to-end.\n");

%% Local functions
function x = preprocessForNet(img, targetSize, imagenetMean, imagenetStd)
% img: HxWx3 double in [0,1]. Returns a formatted dlarray "BCSS" (1x3xSxS).
resized = imresize(img, [targetSize, targetSize]);
normalized = (resized - imagenetMean) ./ imagenetStd;  % HxWx3
chw = permute(normalized, [3 1 2]);  % 3xHxW (channel, spatial, spatial)
withBatch = reshape(chw, [1, size(chw, 1), size(chw, 2), size(chw, 3)]);  % 1x3xHxW
x = dlarray(single(withBatch), "BCSS");
end

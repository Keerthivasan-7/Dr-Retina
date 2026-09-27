function result = runScreeningPipeline(imagePath, nets, temperature)
%RUNSCREENINGPIPELINE Run the full Dr.Retina screening pipeline natively in
%MATLAB on one fundus image: FIQA gate -> calibrated DR grading -> lesion
%segmentation (Optic Disc from one model, MA/HE/EX/SE from another — see
%docs/SIH_SUBMISSION_PLAN.md item 3 for why these are separate models).
%
% nets: struct with fields fiqaNet, drNet, lesionNet (5-channel, OD-focused),
%       lesionNetV2 (4-channel, MA/HE/EX/SE) — see loadScreeningNetworks.m.
% temperature: scalar, from reports/checkpoints/p0_baseline_resnet50/calibration.json.
%
% Returns a struct: fiqaLabel, fiqaProbs, fiqaConf, grade, gradeLabel,
% drConf, drProbs, isReferable, lesionCoveragePct (struct per code),
% lesionMasks (struct per code, logical HxW), overlayRGB (uint8 HxWx3).

icdrClasses = ["No_DR", "Mild", "Moderate", "Severe", "Proliferative_DR"];
fiqaClasses = ["Good", "Usable", "Reject"];
referableThreshold = 2;

imagenetMean = reshape([0.485 0.456 0.406], 1, 1, 3);
imagenetStd  = reshape([0.229 0.224 0.225], 1, 1, 3);

img = imread(imagePath);
if size(img, 3) == 1
    img = repmat(img, 1, 1, 3);
end
img = im2double(img);

fiqaInput = localPreprocess(img, 224, imagenetMean, imagenetStd);
mainInput = localPreprocess(img, 512, imagenetMean, imagenetStd);

% --- FIQA gate ---
fiqaProbs = extractdata(softmax(predict(nets.fiqaNet, fiqaInput)));
[fiqaConf, fiqaIdx] = max(fiqaProbs);
result.fiqaLabel = fiqaClasses(fiqaIdx);
result.fiqaConf = fiqaConf;
result.fiqaProbs = struct(fiqaClasses(1), fiqaProbs(1), fiqaClasses(2), fiqaProbs(2), fiqaClasses(3), fiqaProbs(3));

% --- DR grading (calibrated) ---
drLogits = predict(nets.drNet, mainInput);
drProbs = extractdata(softmax(drLogits / temperature));
[drConf, drIdx] = max(drProbs);
result.grade = drIdx - 1;
result.gradeLabel = icdrClasses(drIdx);
result.drConf = drConf;
result.isReferable = result.grade >= referableThreshold;
result.drProbs = struct();
for i = 1:numel(icdrClasses)
    result.drProbs.(icdrClasses(i)) = drProbs(i);
end

% --- Lesion segmentation: OD from the 5-channel model, MA/HE/EX/SE from v2 ---
odLogits = predict(nets.lesionNet, mainInput);
odProbs = squeezeTo2D(extractdata(sigmoid(odLogits)), 5);
odMask = odProbs(:, :, 5) > 0.5;  % channel order: MA,HE,EX,SE,OD

v2Logits = predict(nets.lesionNetV2, mainInput);
v2Probs = squeezeTo2D(extractdata(sigmoid(v2Logits)), 4);
maMask = v2Probs(:, :, 1) > 0.5;
heMask = v2Probs(:, :, 2) > 0.5;
exMask = v2Probs(:, :, 3) > 0.5;
seMask = v2Probs(:, :, 4) > 0.5;

result.lesionMasks = struct("MA", maMask, "HE", heMask, "EX", exMask, "SE", seMask, "OD", odMask);
codes = ["MA", "HE", "EX", "SE", "OD"];
result.lesionCoveragePct = struct();
for i = 1:numel(codes)
    m = result.lesionMasks.(codes(i));
    result.lesionCoveragePct.(codes(i)) = 100 * sum(m(:)) / numel(m);
end

% --- Overlay image ---
displayImg = imresize(img, [512, 512]);
overlay = im2uint8(displayImg);
colors = struct("MA", [255 0 0], "HE", [255 128 0], "EX", [255 255 0], "SE", [0 255 255], "OD", [0 255 0]);
for i = 1:numel(codes)
    code = codes(i);
    m = result.lesionMasks.(code);
    if any(m(:))
        col = colors.(code);
        for c = 1:3
            channel = overlay(:, :, c);
            channel(m) = uint8(0.6 * double(channel(m)) + 0.4 * col(c));
            overlay(:, :, c) = channel;
        end
    end
end
result.overlayRGB = overlay;
result.originalRGB = im2uint8(displayImg);

end

function x = localPreprocess(img, targetSize, imagenetMean, imagenetStd)
resized = imresize(img, [targetSize, targetSize]);
normalized = (resized - imagenetMean) ./ imagenetStd;
chw = permute(normalized, [3 1 2]);
withBatch = reshape(chw, [1, size(chw, 1), size(chw, 2), size(chw, 3)]);
x = dlarray(single(withBatch), "BCSS");
end

function out = squeezeTo2D(probs, numChannels)
% probs may come back as 1xCxHxW or HxWxC depending on how importNetworkFromONNX
% laid out the "BCSS" output — normalize to HxWxC.
probs = squeeze(probs);
if size(probs, 1) == numChannels
    out = permute(probs, [2 3 1]);  % C x H x W -> H x W x C
else
    out = probs;  % already H x W x C
end
end

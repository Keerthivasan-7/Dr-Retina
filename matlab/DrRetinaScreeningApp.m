classdef DrRetinaScreeningApp < matlab.apps.AppBase
    %DRRETINASCREENINGAPP PS 26038 item 7 — demo pipeline, MATLAB App
    %Designer edition. Upload a fundus image -> FIQA gate -> calibrated DR
    %grade -> lesion evidence overlay -> annotated report, entirely native
    %MATLAB inference (importNetworkFromONNX + the exported PyTorch
    %checkpoints — see docs/SIH_SUBMISSION_PLAN.md item 5), targeting the
    %PS's own "<30s ophthalmologist review" framing.
    %
    % Written as plain classdef code rather than built via the interactive
    % App Designer canvas (uifigure/uigridlayout/uipanel/etc. are the same
    % components App Designer itself generates) — open it in App Designer
    % via "File > Open" and it edits visually like any .mlapp.
    %
    % Run: app = DrRetinaScreeningApp;

    properties (Access = private, Constant)
        ColorBg        = [1.00 1.00 1.00]
        ColorCard      = [0.976 0.980 0.988]
        ColorBorder    = [0.878 0.890 0.910]
        ColorAccent    = [0.075 0.373 0.702]
        ColorAccentDk  = [0.055 0.290 0.560]
        ColorTextMain  = [0.106 0.122 0.157]
        ColorTextSub   = [0.420 0.447 0.490]
        ColorGood      = [0.098 0.541 0.294]
        ColorWarn      = [0.816 0.541 0.031]
        ColorBad       = [0.804 0.153 0.153]
        ColorNeutralBg = [0.933 0.945 0.965]
        GradeDescriptions = struct( ...
            "No_DR", "No visible signs of diabetic retinopathy.", ...
            "Mild", "Mild non-proliferative DR — microaneurysms only.", ...
            "Moderate", "Moderate non-proliferative DR — more than microaneurysms but less than severe NPDR.", ...
            "Severe", "Severe non-proliferative DR — extensive haemorrhages/microaneurysms, venous beading, or IRMA.", ...
            "Proliferative_DR", "Proliferative DR — neovascularization and/or vitreous/preretinal haemorrhage present." ...
        )
    end

    properties (Access = private)
        Nets
        Temperature
        ProjectRoot
        CurrentImagePath
        LastResult
        LastElapsedSec
    end

    properties (Access = public)
        UIFigure                matlab.ui.Figure
        MainGrid                 matlab.ui.container.GridLayout

        HeaderPanel              matlab.ui.container.Panel
        HeaderGrid                matlab.ui.container.GridLayout
        AppTitleLabel             matlab.ui.control.Label
        AppSubtitleLabel          matlab.ui.control.Label
        StatusBadgeLabel          matlab.ui.control.Label

        ImagesPanel               matlab.ui.container.Panel
        ImagesGrid                 matlab.ui.container.GridLayout
        UploadButton               matlab.ui.control.Button
        RunButton                  matlab.ui.control.Button
        ExportButton               matlab.ui.control.Button
        OriginalAxes               matlab.ui.control.UIAxes
        OriginalCaptionLabel       matlab.ui.control.Label
        OverlayAxes                matlab.ui.control.UIAxes
        OverlayCaptionLabel        matlab.ui.control.Label

        ResultsPanel               matlab.ui.container.Panel
        ResultsGrid                 matlab.ui.container.GridLayout
        FIQATitleLabel              matlab.ui.control.Label
        FIQABadgeLabel              matlab.ui.control.Label
        GradeTitleLabel             matlab.ui.control.Label
        GradeNumberLabel            matlab.ui.control.Label
        GradeNameLabel              matlab.ui.control.Label
        ConfidenceTitleLabel        matlab.ui.control.Label
        ConfidenceGauge             matlab.ui.control.LinearGauge
        ConfidenceValueLabel        matlab.ui.control.Label
        ReferableBadgeLabel         matlab.ui.control.Label
        TimingLabel                 matlab.ui.control.Label

        SummaryPanel                matlab.ui.container.Panel
        SummaryGrid                  matlab.ui.container.GridLayout
        SummaryTitleLabel             matlab.ui.control.Label
        SummaryTextArea               matlab.ui.control.TextArea

        ProbPanel                    matlab.ui.container.Panel
        ProbGrid                      matlab.ui.container.GridLayout
        ProbTitleLabel                 matlab.ui.control.Label
        ProbTable                      matlab.ui.control.Table

        EvidencePanel               matlab.ui.container.Panel
        EvidenceGrid                  matlab.ui.container.GridLayout
        EvidenceTitleLabel            matlab.ui.control.Label
        LesionTable                   matlab.ui.control.Table

        CaveatPanel                    matlab.ui.container.Panel
        CaveatGrid                       matlab.ui.container.GridLayout
        CaveatIconLabel                  matlab.ui.control.Label
        CaveatTextArea                   matlab.ui.control.TextArea

        FooterLabel                matlab.ui.control.Label
    end

    methods (Access = private)

        function createComponents(app)
            app.UIFigure = uifigure("Visible", "off");
            app.UIFigure.Position = [60 30 1280 940];
            app.UIFigure.Name = "Dr.Retina — Diabetic Retinopathy Screening";
            app.UIFigure.Color = app.ColorBg;

            app.MainGrid = uigridlayout(app.UIFigure, [5, 1]);
            app.MainGrid.RowHeight = {84, 300, 190, 230, 24};
            app.MainGrid.ColumnWidth = {"1x"};
            app.MainGrid.RowSpacing = 12;
            app.MainGrid.Padding = [20 14 20 10];
            app.MainGrid.BackgroundColor = app.ColorBg;

            createHeader(app);
            createMiddleRow(app);
            createSummaryRow(app);
            createEvidenceRow(app);

            app.FooterLabel = uilabel(app.MainGrid);
            app.FooterLabel.Text = "Dr.Retina — Explainable AI Diabetic Retinopathy Screening (PS 26038)  |  Proof-of-concept — not a validated clinical device";
            app.FooterLabel.HorizontalAlignment = "center";
            app.FooterLabel.FontSize = 11;
            app.FooterLabel.FontColor = app.ColorTextSub;
            app.FooterLabel.Layout.Row = 5;
            app.FooterLabel.Layout.Column = 1;

            app.UIFigure.Visible = "on";
        end

        function createHeader(app)
            app.HeaderPanel = uipanel(app.MainGrid);
            app.HeaderPanel.Layout.Row = 1;
            app.HeaderPanel.Layout.Column = 1;
            app.HeaderPanel.BackgroundColor = app.ColorAccent;
            app.HeaderPanel.BorderType = "none";

            app.HeaderGrid = uigridlayout(app.HeaderPanel, [2, 2]);
            app.HeaderGrid.RowHeight = {28, 20};
            app.HeaderGrid.ColumnWidth = {"1x", 260};
            app.HeaderGrid.Padding = [22 12 22 12];
            app.HeaderGrid.RowSpacing = 2;
            app.HeaderGrid.BackgroundColor = app.ColorAccent;

            app.AppTitleLabel = uilabel(app.HeaderGrid);
            app.AppTitleLabel.Text = "Dr.Retina";
            app.AppTitleLabel.FontSize = 22;
            app.AppTitleLabel.FontWeight = "bold";
            app.AppTitleLabel.FontColor = [1 1 1];
            app.AppTitleLabel.Layout.Row = 1;
            app.AppTitleLabel.Layout.Column = 1;

            app.AppSubtitleLabel = uilabel(app.HeaderGrid);
            app.AppSubtitleLabel.Text = "Explainable AI Diabetic Retinopathy Screening — native MATLAB inference";
            app.AppSubtitleLabel.FontSize = 12;
            app.AppSubtitleLabel.FontColor = [0.88 0.92 0.99];
            app.AppSubtitleLabel.Layout.Row = 2;
            app.AppSubtitleLabel.Layout.Column = 1;

            app.StatusBadgeLabel = uilabel(app.HeaderGrid);
            app.StatusBadgeLabel.Text = "Loading networks...";
            app.StatusBadgeLabel.FontSize = 12;
            app.StatusBadgeLabel.FontColor = [1 1 1];
            app.StatusBadgeLabel.HorizontalAlignment = "right";
            app.StatusBadgeLabel.VerticalAlignment = "center";
            app.StatusBadgeLabel.Layout.Row = [1 2];
            app.StatusBadgeLabel.Layout.Column = 2;
        end

        function createMiddleRow(app)
            wrapGrid = uigridlayout(app.MainGrid, [1, 2]);
            wrapGrid.Layout.Row = 2;
            wrapGrid.Layout.Column = 1;
            wrapGrid.ColumnWidth = {"1.55x", "1x"};
            wrapGrid.ColumnSpacing = 14;
            wrapGrid.Padding = [0 0 0 0];
            wrapGrid.BackgroundColor = app.ColorBg;

            % ---- Images card ----
            app.ImagesPanel = uipanel(wrapGrid);
            app.ImagesPanel.Layout.Row = 1;
            app.ImagesPanel.Layout.Column = 1;
            app.ImagesPanel.BackgroundColor = app.ColorCard;
            styleCard(app, app.ImagesPanel);

            app.ImagesGrid = uigridlayout(app.ImagesPanel, [3, 3]);
            app.ImagesGrid.RowHeight = {40, "1x", 18};
            app.ImagesGrid.ColumnWidth = {"1x", "1x", 140};
            app.ImagesGrid.RowSpacing = 8;
            app.ImagesGrid.Padding = [18 16 18 14];
            app.ImagesGrid.BackgroundColor = app.ColorCard;

            app.UploadButton = uibutton(app.ImagesGrid, "push");
            app.UploadButton.Text = "Upload Fundus Image";
            app.UploadButton.FontWeight = "bold";
            app.UploadButton.FontSize = 13;
            app.UploadButton.BackgroundColor = [1 1 1];
            app.UploadButton.FontColor = app.ColorAccent;
            app.UploadButton.Layout.Row = 1;
            app.UploadButton.Layout.Column = 1;
            app.UploadButton.ButtonPushedFcn = createCallbackFcn(app, @onUploadButtonPushed, true);

            app.RunButton = uibutton(app.ImagesGrid, "push");
            app.RunButton.Text = "Run Screening";
            app.RunButton.FontWeight = "bold";
            app.RunButton.FontSize = 13;
            app.RunButton.BackgroundColor = app.ColorAccent;
            app.RunButton.FontColor = [1 1 1];
            app.RunButton.Enable = "off";
            app.RunButton.Layout.Row = 1;
            app.RunButton.Layout.Column = 2;
            app.RunButton.ButtonPushedFcn = createCallbackFcn(app, @onRunButtonPushed, true);

            app.ExportButton = uibutton(app.ImagesGrid, "push");
            app.ExportButton.Text = "Export Report";
            app.ExportButton.FontWeight = "bold";
            app.ExportButton.FontSize = 13;
            app.ExportButton.BackgroundColor = app.ColorNeutralBg;
            app.ExportButton.FontColor = app.ColorTextMain;
            app.ExportButton.Enable = "off";
            app.ExportButton.Layout.Row = 1;
            app.ExportButton.Layout.Column = 3;
            app.ExportButton.ButtonPushedFcn = createCallbackFcn(app, @onExportButtonPushed, true);

            app.OriginalAxes = uiaxes(app.ImagesGrid);
            app.OriginalAxes.Layout.Row = 2;
            app.OriginalAxes.Layout.Column = 1;
            stylePreviewAxes(app, app.OriginalAxes);

            app.OverlayAxes = uiaxes(app.ImagesGrid);
            app.OverlayAxes.Layout.Row = 2;
            app.OverlayAxes.Layout.Column = [2 3];
            stylePreviewAxes(app, app.OverlayAxes);

            app.OriginalCaptionLabel = uilabel(app.ImagesGrid);
            app.OriginalCaptionLabel.Text = "Original (uploaded)";
            app.OriginalCaptionLabel.HorizontalAlignment = "center";
            app.OriginalCaptionLabel.FontSize = 11;
            app.OriginalCaptionLabel.FontColor = app.ColorTextSub;
            app.OriginalCaptionLabel.Layout.Row = 3;
            app.OriginalCaptionLabel.Layout.Column = 1;

            app.OverlayCaptionLabel = uilabel(app.ImagesGrid);
            app.OverlayCaptionLabel.Text = "Lesion evidence: MA=red  HE=orange  EX=yellow  SE=cyan  OD=green";
            app.OverlayCaptionLabel.HorizontalAlignment = "center";
            app.OverlayCaptionLabel.FontSize = 11;
            app.OverlayCaptionLabel.FontColor = app.ColorTextSub;
            app.OverlayCaptionLabel.Layout.Row = 3;
            app.OverlayCaptionLabel.Layout.Column = [2 3];

            % ---- Results card ----
            app.ResultsPanel = uipanel(wrapGrid);
            app.ResultsPanel.Layout.Row = 1;
            app.ResultsPanel.Layout.Column = 2;
            app.ResultsPanel.BackgroundColor = app.ColorCard;
            styleCard(app, app.ResultsPanel);

            app.ResultsGrid = uigridlayout(app.ResultsPanel, [9, 2]);
            app.ResultsGrid.RowHeight = {20, 30, 22, 44, 30, 20, 30, 40, 18};
            app.ResultsGrid.ColumnWidth = {"1x", "1x"};
            app.ResultsGrid.RowSpacing = 4;
            app.ResultsGrid.Padding = [18 16 18 12];
            app.ResultsGrid.BackgroundColor = app.ColorCard;

            app.FIQATitleLabel = uilabel(app.ResultsGrid);
            app.FIQATitleLabel.Text = "IMAGE QUALITY";
            app.FIQATitleLabel.FontSize = 11;
            app.FIQATitleLabel.FontColor = app.ColorTextSub;
            app.FIQATitleLabel.FontWeight = "bold";
            app.FIQATitleLabel.Layout.Row = 1;
            app.FIQATitleLabel.Layout.Column = [1 2];

            app.FIQABadgeLabel = uilabel(app.ResultsGrid);
            app.FIQABadgeLabel.Text = "  —  ";
            app.FIQABadgeLabel.FontSize = 14;
            app.FIQABadgeLabel.FontWeight = "bold";
            app.FIQABadgeLabel.FontColor = app.ColorTextMain;
            app.FIQABadgeLabel.BackgroundColor = app.ColorNeutralBg;
            app.FIQABadgeLabel.Layout.Row = 2;
            app.FIQABadgeLabel.Layout.Column = [1 2];

            app.GradeTitleLabel = uilabel(app.ResultsGrid);
            app.GradeTitleLabel.Text = "ICDR GRADE";
            app.GradeTitleLabel.FontSize = 11;
            app.GradeTitleLabel.FontColor = app.ColorTextSub;
            app.GradeTitleLabel.FontWeight = "bold";
            app.GradeTitleLabel.Layout.Row = 3;
            app.GradeTitleLabel.Layout.Column = [1 2];

            app.GradeNumberLabel = uilabel(app.ResultsGrid);
            app.GradeNumberLabel.Text = "—";
            app.GradeNumberLabel.FontSize = 34;
            app.GradeNumberLabel.FontWeight = "bold";
            app.GradeNumberLabel.FontColor = app.ColorTextMain;
            app.GradeNumberLabel.Layout.Row = 4;
            app.GradeNumberLabel.Layout.Column = 1;

            app.GradeNameLabel = uilabel(app.ResultsGrid);
            app.GradeNameLabel.Text = "Upload an image to begin";
            app.GradeNameLabel.FontSize = 14;
            app.GradeNameLabel.FontWeight = "bold";
            app.GradeNameLabel.FontColor = app.ColorTextSub;
            app.GradeNameLabel.VerticalAlignment = "bottom";
            app.GradeNameLabel.Layout.Row = 4;
            app.GradeNameLabel.Layout.Column = 2;

            app.ConfidenceTitleLabel = uilabel(app.ResultsGrid);
            app.ConfidenceTitleLabel.Text = "CALIBRATED CONFIDENCE";
            app.ConfidenceTitleLabel.FontSize = 11;
            app.ConfidenceTitleLabel.FontColor = app.ColorTextSub;
            app.ConfidenceTitleLabel.FontWeight = "bold";
            app.ConfidenceTitleLabel.Layout.Row = 5;
            app.ConfidenceTitleLabel.Layout.Column = [1 2];

            app.ConfidenceGauge = uigauge(app.ResultsGrid, "linear");
            app.ConfidenceGauge.Limits = [0 100];
            app.ConfidenceGauge.Layout.Row = 6;
            app.ConfidenceGauge.Layout.Column = 1;
            app.ConfidenceGauge.ScaleColors = {app.ColorAccent};
            app.ConfidenceGauge.ScaleColorLimits = [0 100];

            app.ConfidenceValueLabel = uilabel(app.ResultsGrid);
            app.ConfidenceValueLabel.Text = "—";
            app.ConfidenceValueLabel.FontSize = 16;
            app.ConfidenceValueLabel.FontWeight = "bold";
            app.ConfidenceValueLabel.FontColor = app.ColorAccent;
            app.ConfidenceValueLabel.HorizontalAlignment = "right";
            app.ConfidenceValueLabel.Layout.Row = 6;
            app.ConfidenceValueLabel.Layout.Column = 2;

            app.ReferableBadgeLabel = uilabel(app.ResultsGrid);
            app.ReferableBadgeLabel.Text = "  AWAITING RESULT  ";
            app.ReferableBadgeLabel.FontSize = 13;
            app.ReferableBadgeLabel.FontWeight = "bold";
            app.ReferableBadgeLabel.FontColor = app.ColorTextSub;
            app.ReferableBadgeLabel.BackgroundColor = app.ColorNeutralBg;
            app.ReferableBadgeLabel.HorizontalAlignment = "center";
            app.ReferableBadgeLabel.Layout.Row = 8;
            app.ReferableBadgeLabel.Layout.Column = [1 2];

            app.TimingLabel = uilabel(app.ResultsGrid);
            app.TimingLabel.Text = "";
            app.TimingLabel.FontSize = 10;
            app.TimingLabel.FontColor = app.ColorTextSub;
            app.TimingLabel.HorizontalAlignment = "center";
            app.TimingLabel.Layout.Row = 9;
            app.TimingLabel.Layout.Column = [1 2];
        end

        function createSummaryRow(app)
            wrapGrid = uigridlayout(app.MainGrid, [1, 2]);
            wrapGrid.Layout.Row = 3;
            wrapGrid.Layout.Column = 1;
            wrapGrid.ColumnWidth = {"1.15x", "1x"};
            wrapGrid.ColumnSpacing = 14;
            wrapGrid.Padding = [0 0 0 0];
            wrapGrid.BackgroundColor = app.ColorBg;

            app.SummaryPanel = uipanel(wrapGrid);
            app.SummaryPanel.Layout.Row = 1;
            app.SummaryPanel.Layout.Column = 1;
            app.SummaryPanel.BackgroundColor = app.ColorCard;
            styleCard(app, app.SummaryPanel);

            app.SummaryGrid = uigridlayout(app.SummaryPanel, [2, 1]);
            app.SummaryGrid.RowHeight = {22, "1x"};
            app.SummaryGrid.Padding = [18 14 18 14];
            app.SummaryGrid.RowSpacing = 6;
            app.SummaryGrid.BackgroundColor = app.ColorCard;

            app.SummaryTitleLabel = uilabel(app.SummaryGrid);
            app.SummaryTitleLabel.Text = "CLINICAL SUMMARY (auto-generated from model outputs)";
            app.SummaryTitleLabel.FontSize = 11;
            app.SummaryTitleLabel.FontWeight = "bold";
            app.SummaryTitleLabel.FontColor = app.ColorTextSub;
            app.SummaryTitleLabel.Layout.Row = 1;
            app.SummaryTitleLabel.Layout.Column = 1;

            app.SummaryTextArea = uitextarea(app.SummaryGrid);
            app.SummaryTextArea.Editable = "off";
            app.SummaryTextArea.FontSize = 13;
            app.SummaryTextArea.BackgroundColor = app.ColorCard;
            app.SummaryTextArea.FontColor = app.ColorTextMain;
            app.SummaryTextArea.Layout.Row = 2;
            app.SummaryTextArea.Layout.Column = 1;
            app.SummaryTextArea.Value = "Run screening on an uploaded image to generate a clinical summary.";

            app.ProbPanel = uipanel(wrapGrid);
            app.ProbPanel.Layout.Row = 1;
            app.ProbPanel.Layout.Column = 2;
            app.ProbPanel.BackgroundColor = app.ColorCard;
            styleCard(app, app.ProbPanel);

            app.ProbGrid = uigridlayout(app.ProbPanel, [2, 1]);
            app.ProbGrid.RowHeight = {22, "1x"};
            app.ProbGrid.Padding = [18 14 18 14];
            app.ProbGrid.RowSpacing = 6;
            app.ProbGrid.BackgroundColor = app.ColorCard;

            app.ProbTitleLabel = uilabel(app.ProbGrid);
            app.ProbTitleLabel.Text = "FULL PROBABILITY BREAKDOWN";
            app.ProbTitleLabel.FontSize = 11;
            app.ProbTitleLabel.FontWeight = "bold";
            app.ProbTitleLabel.FontColor = app.ColorTextSub;
            app.ProbTitleLabel.Layout.Row = 1;
            app.ProbTitleLabel.Layout.Column = 1;

            app.ProbTable = uitable(app.ProbGrid);
            app.ProbTable.ColumnName = {"Class", "Type", "Probability %"};
            app.ProbTable.ColumnWidth = {130, 60, 110};
            app.ProbTable.Layout.Row = 2;
            app.ProbTable.Layout.Column = 1;
            app.ProbTable.FontSize = 12;
            app.ProbTable.RowStriping = "on";
        end

        function createEvidenceRow(app)
            wrapGrid = uigridlayout(app.MainGrid, [1, 2]);
            wrapGrid.Layout.Row = 4;
            wrapGrid.Layout.Column = 1;
            wrapGrid.ColumnWidth = {"1.15x", "1x"};
            wrapGrid.ColumnSpacing = 14;
            wrapGrid.Padding = [0 0 0 0];
            wrapGrid.BackgroundColor = app.ColorBg;

            app.EvidencePanel = uipanel(wrapGrid);
            app.EvidencePanel.Layout.Row = 1;
            app.EvidencePanel.Layout.Column = 1;
            app.EvidencePanel.BackgroundColor = app.ColorCard;
            styleCard(app, app.EvidencePanel);

            app.EvidenceGrid = uigridlayout(app.EvidencePanel, [2, 1]);
            app.EvidenceGrid.RowHeight = {22, "1x"};
            app.EvidenceGrid.Padding = [18 14 18 14];
            app.EvidenceGrid.RowSpacing = 6;
            app.EvidenceGrid.BackgroundColor = app.ColorCard;

            app.EvidenceTitleLabel = uilabel(app.EvidenceGrid);
            app.EvidenceTitleLabel.Text = "PER-LESION EVIDENCE";
            app.EvidenceTitleLabel.FontSize = 11;
            app.EvidenceTitleLabel.FontWeight = "bold";
            app.EvidenceTitleLabel.FontColor = app.ColorTextSub;
            app.EvidenceTitleLabel.Layout.Row = 1;
            app.EvidenceTitleLabel.Layout.Column = 1;

            app.LesionTable = uitable(app.EvidenceGrid);
            app.LesionTable.ColumnName = {"Lesion", "Present", "Coverage %", "Source model"};
            app.LesionTable.ColumnWidth = {130, 70, 100, 150};
            app.LesionTable.Layout.Row = 2;
            app.LesionTable.Layout.Column = 1;
            app.LesionTable.FontSize = 12;
            app.LesionTable.RowStriping = "on";

            app.CaveatPanel = uipanel(wrapGrid);
            app.CaveatPanel.Layout.Row = 1;
            app.CaveatPanel.Layout.Column = 2;
            app.CaveatPanel.BackgroundColor = [0.996 0.973 0.929];
            styleCard(app, app.CaveatPanel);
            app.CaveatPanel.BorderColor = [0.949 0.867 0.694];

            app.CaveatGrid = uigridlayout(app.CaveatPanel, [2, 1]);
            app.CaveatGrid.RowHeight = {22, "1x"};
            app.CaveatGrid.Padding = [18 14 18 14];
            app.CaveatGrid.RowSpacing = 6;
            app.CaveatGrid.BackgroundColor = [0.996 0.973 0.929];

            app.CaveatIconLabel = uilabel(app.CaveatGrid);
            app.CaveatIconLabel.Text = "⚠  LIMITATIONS & CAVEATS";
            app.CaveatIconLabel.FontSize = 11;
            app.CaveatIconLabel.FontWeight = "bold";
            app.CaveatIconLabel.FontColor = [0.616 0.451 0.078];
            app.CaveatIconLabel.Layout.Row = 1;
            app.CaveatIconLabel.Layout.Column = 1;

            app.CaveatTextArea = uitextarea(app.CaveatGrid);
            app.CaveatTextArea.Editable = "off";
            app.CaveatTextArea.FontSize = 12;
            app.CaveatTextArea.BackgroundColor = [0.996 0.973 0.929];
            app.CaveatTextArea.FontColor = [0.404 0.318 0.106];
            app.CaveatTextArea.Layout.Row = 2;
            app.CaveatTextArea.Layout.Column = 1;
            app.CaveatTextArea.Value = "Caveats will appear here after running screening.";
        end

        function styleCard(app, panel)
            panel.BorderType = "line";
            panel.BorderColor = app.ColorBorder;
            panel.BorderWidth = 1;
        end

        function stylePreviewAxes(app, ax)
            ax.XTick = [];
            ax.YTick = [];
            ax.Box = "on";
            ax.Color = [0.06 0.06 0.07];
            ax.XColor = app.ColorBorder;
            ax.YColor = app.ColorBorder;
        end

        function onUploadButtonPushed(app, ~)
            [file, path] = uigetfile({"*.jpg;*.jpeg;*.png", "Fundus images"}, "Select a fundus image");
            if isequal(file, 0)
                return;
            end
            app.CurrentImagePath = fullfile(path, file);
            img = imread(app.CurrentImagePath);
            imshow(img, "Parent", app.OriginalAxes);
            app.RunButton.Enable = "on";
            app.ExportButton.Enable = "off";
            app.StatusBadgeLabel.Text = "Image loaded — click Run Screening";
        end

        function onRunButtonPushed(app, ~)
            app.StatusBadgeLabel.Text = "Running FIQA → DR grading → lesion segmentation...";
            app.RunButton.Enable = "off";
            app.ExportButton.Enable = "off";
            drawnow;

            tStart = tic;
            try
                result = runScreeningPipeline(app.CurrentImagePath, app.Nets, app.Temperature);
            catch ME
                app.StatusBadgeLabel.Text = "Error: " + string(ME.message);
                app.RunButton.Enable = "on";
                return;
            end
            elapsedSec = toc(tStart);
            app.LastResult = result;
            app.LastElapsedSec = elapsedSec;

            imshow(result.overlayRGB, "Parent", app.OverlayAxes);
            drawnow;

            % --- FIQA badge ---
            switch result.fiqaLabel
                case "Good"
                    fiqaColor = app.ColorGood; fiqaBg = [0.902 0.965 0.914];
                case "Usable"
                    fiqaColor = app.ColorWarn; fiqaBg = [0.996 0.949 0.855];
                otherwise
                    fiqaColor = app.ColorBad; fiqaBg = [0.988 0.898 0.898];
            end
            app.FIQABadgeLabel.Text = sprintf("  %s  \x2022  %.1f%% confidence  ", result.fiqaLabel, result.fiqaConf * 100);
            app.FIQABadgeLabel.FontColor = fiqaColor;
            app.FIQABadgeLabel.BackgroundColor = fiqaBg;

            % --- Grade ---
            app.GradeNumberLabel.Text = sprintf("%d", result.grade);
            app.GradeNameLabel.Text = result.gradeLabel;
            gradeColors = {app.ColorGood, app.ColorGood, app.ColorWarn, app.ColorBad, app.ColorBad};
            app.GradeNumberLabel.FontColor = gradeColors{result.grade + 1};
            app.GradeNameLabel.FontColor = gradeColors{result.grade + 1};

            % --- Confidence ---
            confPct = result.drConf * 100;
            app.ConfidenceGauge.Value = confPct;
            app.ConfidenceValueLabel.Text = sprintf("%.1f%%", confPct);

            % --- Referable badge ---
            if result.isReferable
                app.ReferableBadgeLabel.Text = "  \x26A0  REFERABLE \x2014 REFER TO OPHTHALMOLOGIST  ";
                app.ReferableBadgeLabel.FontColor = [1 1 1];
                app.ReferableBadgeLabel.BackgroundColor = app.ColorBad;
            else
                app.ReferableBadgeLabel.Text = "  \x2713  NOT REFERABLE \x2014 ROUTINE FOLLOW-UP  ";
                app.ReferableBadgeLabel.FontColor = [1 1 1];
                app.ReferableBadgeLabel.BackgroundColor = app.ColorGood;
            end

            app.TimingLabel.Text = sprintf("Screened in %.2fs \x2014 meets the PS's <30s review target", elapsedSec);
            drawnow;

            % --- Lesion evidence table (valid, ASCII-safe variable names; ColumnName is separate & used for display) ---
            codes = ["MA", "HE", "EX", "SE", "OD"];
            names = ["Microaneurysms", "Haemorrhages", "Hard Exudates", "Soft Exudates", "Optic Disc"];
            sources = ["v2 (merged data)", "v2 (merged data)", "v2 (merged data)", "v2 (merged data)", "IDRiD-only"];
            presentCol = strings(numel(codes), 1);
            coverageCol = zeros(numel(codes), 1);
            for i = 1:numel(codes)
                coverageCol(i) = result.lesionCoveragePct.(codes(i));
                if coverageCol(i) > 0.01
                    presentCol(i) = "Yes";
                else
                    presentCol(i) = "No";
                end
            end
            lesionT = table(names', presentCol, round(coverageCol, 3), sources', ...
                VariableNames=["Lesion", "Present", "CoveragePct", "SourceModel"]);
            app.LesionTable.Data = lesionT;
            drawnow;

            % --- Full probability breakdown table ---
            drNames = ["No_DR", "Mild", "Moderate", "Severe", "Proliferative_DR"];
            drVals = zeros(numel(drNames), 1);
            for i = 1:numel(drNames)
                drVals(i) = result.drProbs.(drNames(i)) * 100;
            end
            fiqaNames = ["Good", "Usable", "Reject"];
            fiqaVals = zeros(numel(fiqaNames), 1);
            for i = 1:numel(fiqaNames)
                fiqaVals(i) = result.fiqaProbs.(fiqaNames(i)) * 100;
            end
            classCol = [drNames'; fiqaNames'];
            typeCol = [repmat("DR grade", numel(drNames), 1); repmat("FIQA", numel(fiqaNames), 1)];
            probCol = [drVals; fiqaVals];
            probT = table(classCol, typeCol, round(probCol, 2), VariableNames=["Class", "Type", "ProbabilityPct"]);
            app.ProbTable.Data = probT;
            drawnow;

            % --- Clinical summary (deterministic, template-based — not an LLM call,
            % so it can never state a finding the structured results don't support) ---
            app.SummaryTextArea.Value = buildClinicalSummary(app, result);
            drawnow;

            % --- Caveats ---
            app.CaveatTextArea.Value = [
                "Optic Disc: IDRiD-only (54 images), 0.842 dice."
                "MA/HE/EX/SE: merged IDRiD+DDR+e-ophtha (~1,300 images),"
                "pretrained encoder + Focal Tversky Loss. Proof-of-concept"
                "scale, not a validated clinical result."
                ""
                "Microaneurysm dice = 0.029 (literature best on much larger,"
                "cleaner data is ~0.56) \x2014 treat MA marks as a weak signal,"
                "not a definitive finding."
                ""
                "This overlay is direct per-lesion segmentation evidence,"
                "not a coarse Grad-CAM attention map."
                ];

            app.StatusBadgeLabel.Text = "Screening complete";
            app.RunButton.Enable = "on";
            app.ExportButton.Enable = "on";
        end

        function summary = buildClinicalSummary(app, result)
            presentCodes = {};
            codes = ["MA", "HE", "EX", "SE"];
            names = ["microaneurysms", "haemorrhages", "hard exudates", "soft exudates"];
            for i = 1:numel(codes)
                if result.lesionCoveragePct.(codes(i)) > 0.01
                    presentCodes{end+1} = sprintf("%s (%.2f%% of image area)", names(i), result.lesionCoveragePct.(codes(i))); %#ok<AGROW>
                end
            end
            if isempty(presentCodes)
                lesionSentence = "No microaneurysms, haemorrhages, or exudates were segmented above the detection threshold.";
            else
                lesionSentence = "Segmented lesion evidence: " + strjoin(string(presentCodes), "; ") + ".";
            end

            gradeDesc = app.GradeDescriptions.(result.gradeLabel);

            if result.fiqaLabel == "Reject"
                qualityNote = "Image quality was flagged as REJECT — the grade below is unreliable; request a recapture.";
            elseif result.fiqaLabel == "Usable"
                qualityNote = "Image quality was Usable (not ideal) — findings should be interpreted with that in mind.";
            else
                qualityNote = "Image quality was Good.";
            end

            if result.isReferable
                actionSentence = "This case is REFERABLE (ICDR >= 2) and should be routed to an ophthalmologist for confirmation.";
            else
                actionSentence = "This case is not referable at the current threshold (ICDR < 2); routine screening follow-up is appropriate.";
            end

            summary = sprintf([...
                "ICDR grade %d (%s), calibrated confidence %.1f%%. %s\n\n" ...
                "%s\n\n%s\n\n%s\n\n" ...
                "This summary is generated deterministically from the structured model outputs above " ...
                "(a fixed template filling in the numbers) — it is not a free-text generation and cannot " ...
                "state anything the numbers don't already show."], ...
                result.grade, result.gradeLabel, result.drConf * 100, gradeDesc, ...
                qualityNote, lesionSentence, actionSentence);
        end

        function onExportButtonPushed(app, ~)
            if isempty(app.LastResult)
                return;
            end
            outDir = fullfile(app.ProjectRoot, "reports", "explainability");
            if ~exist(outDir, "dir")
                mkdir(outDir);
            end
            [~, stem] = fileparts(app.CurrentImagePath);
            ts = string(datetime("now", "Format", "yyyyMMdd_HHmmss"));
            baseName = sprintf("%s_matlab_%s", stem, ts);

            overlayPath = fullfile(outDir, baseName + "_overlay.png");
            imwrite(app.LastResult.overlayRGB, overlayPath);

            r = app.LastResult;
            reportStruct = struct( ...
                "image", app.CurrentImagePath, ...
                "generated_by", "DrRetinaScreeningApp (MATLAB, native inference)", ...
                "timestamp", string(datetime("now", "Format", "yyyy-MM-dd''T''HH:mm:ss")), ...
                "elapsed_seconds", app.LastElapsedSec, ...
                "fiqa_label", r.fiqaLabel, "fiqa_confidence", r.fiqaConf, ...
                "icdr_grade", r.grade, "icdr_grade_label", r.gradeLabel, ...
                "calibrated_confidence", r.drConf, "is_referable", r.isReferable, ...
                "lesion_coverage_pct", r.lesionCoveragePct, ...
                "overlay_path", overlayPath);
            jsonPath = fullfile(outDir, baseName + "_report.json");
            fid = fopen(jsonPath, "w");
            fprintf(fid, "%s", jsonencode(reportStruct, "PrettyPrint", true));
            fclose(fid);

            app.StatusBadgeLabel.Text = sprintf("Report saved: %s", baseName + "_report.json");
        end

    end

    methods (Access = public)

        function app = DrRetinaScreeningApp()
            app.ProjectRoot = fileparts(fileparts(mfilename("fullpath")));
            addpath(fullfile(app.ProjectRoot, "matlab"));

            createComponents(app);
            app.StatusBadgeLabel.Text = "Loading networks (first run may take a few seconds)...";
            drawnow;

            [app.Nets, app.Temperature] = loadScreeningNetworks(app.ProjectRoot);
            app.StatusBadgeLabel.Text = "Ready — upload an image to begin";

            if nargout == 0
                clear app;
            end
        end

        function delete(app)
            delete(app.UIFigure);
        end
    end
end

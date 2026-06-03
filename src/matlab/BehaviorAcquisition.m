% =========================================================================
%  BehaviorAcquisition.m
%  ScanImage 統合 行動データ取得システム
% =========================================================================
%
%  設計方針:
%    - ScanImage (MATLAB) の中で全データを取得 → 競合なし
%    - User Functions の frameAcquired / acqDone イベントで
%      フレームカウントを自動記録
%    - NI-DAQmx を MATLAB から直接操作し、行動データ (AI) を連続取得
%    - 保存はチャンクごとに HDF5 へ書き出す「ストリーミング保存」
%      → メモリにデータを溜め込まない
%
%  使い方:
%    >> baq = BehaviorAcquisition();       % インスタンス作成
%    >> baq.setup();                       % DAQ タスク初期化
%    >> baq.registerWithScanImage();       % ScanImage イベントに登録
%    >> baq.start();                       % 取得開始
%    ...実験中 ScanImage で Grab/Loop を操作...
%    >> baq.stop();                        % 取得停止・ファイルを閉じる
%    >> baq.report();                      % サマリー表示
%
%  依存:
%    - ScanImage (hSI が base workspace にあること)
%    - NI-DAQmx (Data Acquisition Toolbox)
%    - MATLAB R2019a 以降推奨 (HDF5 書き込み API)
%
% =========================================================================

classdef BehaviorAcquisition < handle

    % ── 設定プロパティ (実験前に編集) ────────────────────────────────
    properties
        % ---- サンプリング ------------------------------------------------
        sampleRate      double = 2000       % [Hz] 1-5 kHz
        chunkDuration   double = 0.5        % [s]  1チャンクのサイズ (= HDF5 書込み間隔)
        
        % ---- チャンネル設定 (name, physicalChannel, minV, maxV) ----------
        % vDAQ の Aux IO または別 NI DAQ を使う
        channelDefs = {
            'velocity',     'Dev1/ai0',  -10,  10;   % ロータリーエンコーダ
            'lick',         'Dev1/ai1',    0,   5;   % 舐め検出
            'pupil_trig',   'Dev1/ai2',    0,   5;   % 瞳孔カメラトリガー
            'reward_valve', 'Dev1/ai3',    0,   5;   % 報酬バルブ
            'frame_clock',  'Dev1/ai4',    0,   5;   % ScanImage フレームクロック TTL コピー
            'visual_stim',  'Dev1/ai5',    0,   5;   % 視覚刺激タイミング
        };
        
        % ---- 保存 --------------------------------------------------------
        outputDir       char   = 'C:\data'
        sessionName     char   = ''         % 空 → タイムスタンプ自動
        
        % ---- フレームトリガー検出 ----------------------------------------
        frameTrigChannel  char   = 'frame_clock'   % 上記 channelDefs の name
        frameTrigThresh   double = 2.5             % 閾値 [V]
    end

    % ── 内部プロパティ ────────────────────────────────────────────────
    properties (Access = private)
        % DAQ
        daqTask             % NI-DAQmx Task オブジェクト
        daqReader           % AnalogMultiChannelReader

        % ファイル
        h5File              % HDF5 ファイルパス
        h5DatasetIds        % struct: channel name → dataset id
        chunkSamples        % チャンクあたりのサンプル数
        totalWritten   = 0  % 書き込み済みサンプル数
        h5MaxSamples   = 0  % HDF5 の現在のデータセットサイズ (拡張用)
        h5ExtendStep        % 一度に拡張するサンプル数

        % フレームログ
        frameLog = struct(...
            'frameNumber',  [], ...  % ScanImage フレーム番号
            'wallTime',     [], ...  % wall clock (datetime)
            'sampleIndex',  [] ...   % 対応する行動データのサンプルインデックス（推定）
        );
        frameCount     = 0

        % 状態
        isRunning      = false
        startWallTime
        listeners = {}      % ScanImage イベントリスナー
        
        % コールバック用バッファ
        cbBuffer            % (n_ch × chunkSamples) 再利用バッファ
    end

    % =====================================================================
    methods

        % ── コンストラクタ ────────────────────────────────────────────
        function obj = BehaviorAcquisition()
            fprintf('[BehaviorAcq] インスタンス作成\n');
        end

        % ── セットアップ ─────────────────────────────────────────────
        function setup(obj)
            % NI-DAQmx タスクを初期化する
            obj.chunkSamples = round(obj.sampleRate * obj.chunkDuration);
            nCh = size(obj.channelDefs, 1);
            obj.cbBuffer = zeros(nCh, obj.chunkSamples);

            % タスク作成
            obj.daqTask = daq.createSession('ni');
            obj.daqTask.Rate = obj.sampleRate;
            obj.daqTask.IsContinuous = true;
            obj.daqTask.NotifyWhenDataAvailableExceeds = obj.chunkSamples;

            % チャンネル追加
            for i = 1:nCh
                ch = obj.daqTask.addAnalogInputChannel(...
                    strtok(obj.channelDefs{i,2},'/'), ...   % デバイス名 "Dev1"
                    obj.channelDefs{i,2}, ...               % チャンネル名 "Dev1/ai0"
                    'Voltage');
                ch.Name = obj.channelDefs{i,1};
                ch.Range = [obj.channelDefs{i,3}, obj.channelDefs{i,4}];
                fprintf('  AI ch: %-20s  ← %-12s  [%+.0f, %+.0f] V\n', ...
                    obj.channelDefs{i,1}, obj.channelDefs{i,2}, ...
                    obj.channelDefs{i,3}, obj.channelDefs{i,4});
            end

            % コールバック登録
            addlistener(obj.daqTask, 'DataAvailable', ...
                @(src,evt) obj.onDataAvailable(src, evt));
            addlistener(obj.daqTask, 'ErrorOccurred', ...
                @(src,evt) obj.onError(src, evt));

            fprintf('[BehaviorAcq] セットアップ完了  Fs=%g Hz  chunk=%d smp (%.0f ms)\n', ...
                obj.sampleRate, obj.chunkSamples, obj.chunkDuration * 1000);
        end

        % ── ScanImage イベント登録 ────────────────────────────────────
        function registerWithScanImage(obj)
            % base workspace の hSI に接続する
            if ~evalin('base', 'exist(''hSI'',''var'')')
                warning('[BehaviorAcq] hSI が base workspace にありません。ScanImage を起動してください。');
                return;
            end
            hSI = evalin('base', 'hSI');

            % frameAcquired イベント
            L1 = addlistener(hSI.hUserFunctions, 'frameAcquired', ...
                @(src,evt) obj.onFrameAcquired(src, evt));
            % acqDone イベント（取得終了を検知）
            L2 = addlistener(hSI.hUserFunctions, 'acqDone', ...
                @(src,evt) obj.onAcqDone(src, evt));

            obj.listeners = {L1, L2};
            fprintf('[BehaviorAcq] ScanImage イベントに登録しました。\n');
        end

        % ── 開始 ─────────────────────────────────────────────────────
        function start(obj)
            if obj.isRunning
                warning('[BehaviorAcq] すでに実行中です。');
                return;
            end

            % 出力ファイルパス決定
            if isempty(obj.sessionName)
                obj.sessionName = datestr(now, 'yyyymmdd_HHMMSS');
            end
            outPath = fullfile(obj.outputDir, obj.sessionName);
            if ~exist(outPath, 'dir'), mkdir(outPath); end
            obj.h5File = fullfile(outPath, 'behavior.h5');

            % HDF5 ファイル初期化
            obj.initH5();

            % 設定を JSON で保存
            obj.saveConfig(outPath);

            obj.isRunning = true;
            obj.startWallTime = datetime('now');
            obj.totalWritten  = 0;
            obj.frameCount    = 0;
            obj.frameLog.frameNumber = [];
            obj.frameLog.wallTime    = datetime.empty;
            obj.frameLog.sampleIndex = [];

            obj.daqTask.startBackground();
            fprintf('[BehaviorAcq] ★ 取得開始  %s\n', obj.sessionName);
        end

        % ── 停止 ─────────────────────────────────────────────────────
        function stop(obj)
            if ~obj.isRunning, return; end

            obj.daqTask.stop();
            obj.isRunning = false;

            elapsed = seconds(datetime('now') - obj.startWallTime);
            fprintf('[BehaviorAcq] 停止  (%.1f s  %d samples  %d frames)\n', ...
                elapsed, obj.totalWritten, obj.frameCount);

            % HDF5 のデータセットを実際のサイズにトリミング
            obj.trimH5();

            % フレームログを HDF5 に書き込む
            obj.writeFrameLog();

            fprintf('[BehaviorAcq] 保存完了 → %s\n', obj.h5File);
        end

        % ── サマリー ─────────────────────────────────────────────────
        function report(obj)
            fprintf('\n============================================\n');
            fprintf('  セッション : %s\n', obj.sessionName);
            fprintf('  出力ファイル: %s\n', obj.h5File);
            fprintf('  チャンネル  : %d\n', size(obj.channelDefs,1));
            fprintf('  サンプル数  : %d\n', obj.totalWritten);
            fprintf('  フレーム数  : %d\n', obj.frameCount);
            fprintf('  Fs          : %g Hz\n', obj.sampleRate);
            if obj.totalWritten > 0 && obj.sampleRate > 0
                fprintf('  時間        : %.2f s\n', obj.totalWritten / obj.sampleRate);
            end
            fprintf('============================================\n\n');
        end

        % ── デストラクタ ─────────────────────────────────────────────
        function delete(obj)
            if obj.isRunning
                obj.stop();
            end
            % リスナー解除
            for i = 1:numel(obj.listeners)
                delete(obj.listeners{i});
            end
            if ~isempty(obj.daqTask) && isvalid(obj.daqTask)
                delete(obj.daqTask);
            end
        end

    end % methods

    % =====================================================================
    methods (Access = private)

        % ── DAQ コールバック: データ取得 ──────────────────────────────
        function onDataAvailable(obj, ~, evt)
            % evt.Data : (chunkSamples × nChannels)  MATLAB Data Acq Toolbox の規則
            chunk = evt.Data';   % → (nChannels × chunkSamples)
            obj.appendToH5(chunk);
        end

        % ── DAQ エラー ────────────────────────────────────────────────
        function onError(obj, ~, evt)
            fprintf('[BehaviorAcq] !! DAQ エラー: %s\n', evt.Error.message);
        end

        % ── ScanImage: フレーム取得イベント ───────────────────────────
        function onFrameAcquired(obj, src, ~)
            if ~obj.isRunning, return; end
            obj.frameCount = obj.frameCount + 1;

            % フレーム番号を ScanImage から取得
            hSI = src.hSI;
            fn = hSI.hScan2D.frameAcqFcnDecimationFactor * obj.frameCount;

            % このフレームに対応する行動データのサンプルインデックス（推定）
            sampleIdx = obj.totalWritten;   % フレーム検出時点での書込み済みサンプル数

            obj.frameLog.frameNumber(end+1) = fn;
            obj.frameLog.wallTime(end+1)    = datetime('now');
            obj.frameLog.sampleIndex(end+1) = sampleIdx;
        end

        % ── ScanImage: 取得完了イベント ───────────────────────────────
        function onAcqDone(obj, ~, ~)
            fprintf('[BehaviorAcq] ScanImage 取得完了イベント受信\n');
            if obj.isRunning
                pause(0.2);   % 最後のデータがキューに残るまで少し待つ
                obj.stop();
            end
        end

        % ── HDF5 初期化（拡張可能データセット） ──────────────────────
        function initH5(obj)
            nCh    = size(obj.channelDefs, 1);
            % 初期サイズ = 30 秒分、拡張ステップも同じ
            initSamples = round(obj.sampleRate * 30);
            obj.h5ExtendStep = initSamples;
            obj.h5MaxSamples = initSamples;

            % ファイル作成
            fid = H5F.create(obj.h5File, 'H5F_ACC_TRUNC', ...
                'H5P_DEFAULT', 'H5P_DEFAULT');

            % ── ルート属性 ──────────────────────────────────────────
            obj.writeH5Attr(fid, 'sample_rate',   obj.sampleRate);
            obj.writeH5Attr(fid, 'session_name',  obj.sessionName);
            obj.writeH5Attr(fid, 'start_time',    datestr(now));
            obj.writeH5Attr(fid, 'n_channels',    nCh);

            % ── analog グループ ──────────────────────────────────────
            gid = H5G.create(fid, 'analog', 'H5P_DEFAULT', ...
                'H5P_DEFAULT', 'H5P_DEFAULT');

            % チャンクド・拡張可能データセットを作成
            obj.h5DatasetIds = struct();
            for i = 1:nCh
                name = obj.channelDefs{i,1};
                dsetId = obj.createExtendableDataset(gid, name, initSamples);
                % チャンネル属性
                obj.writeH5DatasetAttr(dsetId, 'physical_channel', obj.channelDefs{i,2});
                obj.writeH5DatasetAttr(dsetId, 'min_val', obj.channelDefs{i,3});
                obj.writeH5DatasetAttr(dsetId, 'max_val', obj.channelDefs{i,4});
                obj.h5DatasetIds.(name) = dsetId;
            end
            H5G.close(gid);

            % ── time データセット (拡張可能) ────────────────────────
            obj.h5DatasetIds.time = obj.createExtendableDataset(fid, 'time', initSamples);
            obj.writeH5DatasetAttr(obj.h5DatasetIds.time, 'unit', 's');

            H5F.close(fid);
            fprintf('[BehaviorAcq] HDF5 初期化: %s\n', obj.h5File);
        end

        % ── HDF5 への追記（ストリーミング保存） ──────────────────────
        function appendToH5(obj, chunk)
            % chunk: (nCh × nSamples)
            nNew  = size(chunk, 2);
            nCh   = size(obj.channelDefs, 1);
            start = obj.totalWritten;

            % 必要なら HDF5 データセットを拡張
            if start + nNew > obj.h5MaxSamples
                newSize = obj.h5MaxSamples + obj.h5ExtendStep;
                while newSize < start + nNew
                    newSize = newSize + obj.h5ExtendStep;
                end
                obj.extendH5Datasets(newSize);
                obj.h5MaxSamples = newSize;
            end

            % 各チャンネルを書き込む
            for i = 1:nCh
                name  = obj.channelDefs{i,1};
                dsetId = obj.h5DatasetIds.(name);
                % HDF5 書き込み: スラブ選択
                h5write(obj.h5File, ['/analog/' name], ...
                    single(chunk(i,:)), [start+1], [nNew]);
            end

            % time ベクトル書き込み
            t = (start : start+nNew-1)' / obj.sampleRate;
            h5write(obj.h5File, '/time', single(t), [start+1], [nNew]);

            obj.totalWritten = start + nNew;
        end

        % ── HDF5 データセットをトリミング ────────────────────────────
        function trimH5(obj)
            nCh = size(obj.channelDefs, 1);
            actual = obj.totalWritten;
            for i = 1:nCh
                name = obj.channelDefs{i,1};
                fid  = H5F.open(obj.h5File, 'H5F_ACC_RDWR', 'H5P_DEFAULT');
                gid  = H5G.open(fid, 'analog');
                did  = H5D.open(gid, name);
                H5D.set_extent(did, actual);
                H5D.close(did);
                H5G.close(gid);
                H5F.close(fid);
            end
            % time もトリム
            fid = H5F.open(obj.h5File, 'H5F_ACC_RDWR', 'H5P_DEFAULT');
            did = H5D.open(fid, 'time');
            H5D.set_extent(did, actual);
            H5D.close(did);
            H5F.close(fid);
        end

        % ── フレームログを HDF5 に書き込む ───────────────────────────
        function writeFrameLog(obj)
            if isempty(obj.frameLog.frameNumber), return; end
            n = numel(obj.frameLog.frameNumber);
            h5create(obj.h5File, '/frame_log/frame_number',   [n], 'Datatype', 'int32');
            h5create(obj.h5File, '/frame_log/sample_index',   [n], 'Datatype', 'int64');
            h5create(obj.h5File, '/frame_log/time_s',         [n], 'Datatype', 'single');

            h5write(obj.h5File, '/frame_log/frame_number',   int32(obj.frameLog.frameNumber));
            h5write(obj.h5File, '/frame_log/sample_index',   int64(obj.frameLog.sampleIndex));
            h5write(obj.h5File, '/frame_log/time_s', ...
                single(double(obj.frameLog.sampleIndex) / obj.sampleRate));

            h5writeatt(obj.h5File, '/frame_log', 'n_frames', n);
            fprintf('[BehaviorAcq] フレームログ書き込み完了  %d フレーム\n', n);
        end

        % ── 設定保存 ─────────────────────────────────────────────────
        function saveConfig(obj, outPath)
            cfg.sample_rate  = obj.sampleRate;
            cfg.session_name = obj.sessionName;
            cfg.start_time   = datestr(now);
            cfg.channels = struct();
            for i = 1:size(obj.channelDefs,1)
                cfg.channels(i).name     = obj.channelDefs{i,1};
                cfg.channels(i).physical = obj.channelDefs{i,2};
                cfg.channels(i).min_v    = obj.channelDefs{i,3};
                cfg.channels(i).max_v    = obj.channelDefs{i,4};
            end
            jsonStr = jsonencode(cfg);
            fid = fopen(fullfile(outPath, 'config.json'), 'w');
            fwrite(fid, jsonStr);
            fclose(fid);
        end

        % ── HDF5 ヘルパー: 拡張可能データセット作成 ─────────────────
        function did = createExtendableDataset(~, locId, name, initSize)
            % float32, チャンク圧縮 (gzip level 4), 無制限拡張
            type_id  = H5T.copy('H5T_NATIVE_FLOAT');
            dims     = uint64(initSize);
            maxdims  = uint64(H5ML.get_constant_value('H5S_UNLIMITED'));
            space_id = H5S.create_simple(1, dims, maxdims);

            dcpl = H5P.create('H5P_DATASET_CREATE');
            chunk = uint64(min(initSize, 4096));  % チャンクサイズ
            H5P.set_chunk(dcpl, 1, chunk);
            H5P.set_deflate(dcpl, 4);  % gzip level 4

            did = H5D.create(locId, name, type_id, space_id, ...
                'H5P_DEFAULT', dcpl, 'H5P_DEFAULT');
            H5P.close(dcpl);
            H5S.close(space_id);
            H5T.close(type_id);
        end

        function extendH5Datasets(obj, newSize)
            nCh = size(obj.channelDefs, 1);
            fid = H5F.open(obj.h5File, 'H5F_ACC_RDWR', 'H5P_DEFAULT');
            gid = H5G.open(fid, 'analog');
            for i = 1:nCh
                did = H5D.open(gid, obj.channelDefs{i,1});
                H5D.set_extent(did, uint64(newSize));
                H5D.close(did);
            end
            H5G.close(gid);
            did = H5D.open(fid, 'time');
            H5D.set_extent(did, uint64(newSize));
            H5D.close(did);
            H5F.close(fid);
        end

        function writeH5Attr(~, locId, attrName, value)
            if ischar(value)
                tid = H5T.copy('H5T_C_S1');
                H5T.set_size(tid, numel(value));
                sid = H5S.create('H5S_SCALAR');
                aid = H5A.create(locId, attrName, tid, sid, 'H5P_DEFAULT');
                H5A.write(aid, tid, value);
                H5A.close(aid); H5S.close(sid); H5T.close(tid);
            else
                sid = H5S.create('H5S_SCALAR');
                tid = H5T.copy('H5T_NATIVE_DOUBLE');
                aid = H5A.create(locId, attrName, tid, sid, 'H5P_DEFAULT');
                H5A.write(aid, tid, double(value));
                H5A.close(aid); H5S.close(sid); H5T.close(tid);
            end
        end

        function writeH5DatasetAttr(obj, did, attrName, value)
            obj.writeH5Attr(did, attrName, value);
        end

    end % private methods
end

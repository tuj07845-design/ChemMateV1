function draw_dispatch(job_dir)
%DRAW_DISPATCH  ChemMate V1 MATLAB 唯一入口
%   Python:  eng.draw_dispatch(job_dir)
%   CLI:     matlab -batch "addpath('.../matlab/draw'); draw_dispatch('jobs/draw_xxx')"

    % ---------- 入参校验：job_dir 是必需的 ----------
    if nargin < 1 || strlength(string(job_dir)) == 0
        error('draw_dispatch:JobDirRequired', 'job_dir is required');
    end

    % 约定 job 目录里放三个文件：
    %   request.json（绘图请求） / data.csv（绘图数据） / result.json（结果回写）
    job_dir = char(job_dir);
    req_path  = fullfile(job_dir, 'request.json');
    data_path = fullfile(job_dir, 'data.csv');
    res_path  = fullfile(job_dir, 'result.json');

    % ---------- 前置检查：缺输入文件直接写失败结果 ----------
    if ~isfile(req_path)
        write_result(res_path, false, 'matlab_failed', 'missing request.json', '', struct());
        return;
    end
    if ~isfile(data_path)
        write_result(res_path, false, 'matlab_failed', 'missing data.csv', '', struct());
        return;
    end

    % ---------- 解析请求：request.json 必须是合法 JSON ----------
    try
        req = jsondecode(fileread(req_path));
    catch ME
        write_result(res_path, false, 'matlab_failed', ...
            ['invalid request.json: ' ME.message], '', struct());
        return;
    end

    % ---------- plot_type 必须存在；export 只允许 png/svg ----------
    if ~isfield(req, 'plot_type') || strlength(string(req.plot_type)) == 0
        write_result(res_path, false, 'spec_invalid', 'plot_type is required', '', struct());
        return;
    end

    plot_type = lower(strtrim(char(string(req.plot_type))));
    export_fmt = 'png';
    if isfield(req, 'export') && strlength(string(req.export)) > 0
        export_fmt = lower(strtrim(char(string(req.export))));
    end
    if ~ismember(export_fmt, {'png', 'svg'})
        write_result(res_path, false, 'spec_invalid', ...
            'export must be png or svg', '', struct());
        return;
    end

    fig_path = fullfile(job_dir, ['figure.' export_fmt]);

    % ---------- 读数据：保留原始列名，字符串按 string 读入 ----------
    try
        tbl = readtable(data_path, 'TextType', 'string', 'VariableNamingRule', 'preserve');
    catch ME
        write_result(res_path, false, 'matlab_failed', ...
            ['failed to read data.csv: ' ME.message], '', struct());
        return;
    end

    if height(tbl) == 0
        write_result(res_path, false, 'data_not_found', 'data.csv has no rows', '', struct());
        return;
    end

    % ---------- 按 plot_type 分发到具体绘图函数 ----------
    %   stream_tp          流股温度-压力
    %   stream_composition 物流组成
    %   component_track    组分沿流股分布
    %   balance_check      设备进出衡算
    try
        switch plot_type
            case 'stream_tp'
                meta = plot_stream_TP(tbl, req, fig_path);
            case 'stream_composition'
                meta = plot_stream_composition(tbl, req, fig_path);
            case 'component_track'
                meta = plot_component_track(tbl, req, fig_path);
            case 'balance_check'
                meta = plot_balance_check(tbl, req, fig_path);
            otherwise
                write_result(res_path, false, 'unknown_plot_type', ...
                    sprintf('unknown plot_type: %s', plot_type), '', struct());
                return;
        end

        if ~isfile(fig_path)
            write_result(res_path, false, 'matlab_failed', ...
                'plot function finished but figure file missing', '', struct());
            return;
        end

        write_result(res_path, true, '', '', fig_path, meta);
    catch ME
        % 按错误标识归类：spec_invalid=参数问题 / data_not_found=数据问题 / 其它=MATLAB 内部失败
        code = 'matlab_failed';
        if contains(ME.identifier, 'spec_invalid') || startsWith(ME.message, 'spec_invalid')
            code = 'spec_invalid';
        elseif contains(ME.identifier, 'data_not_found') || startsWith(ME.message, 'data_not_found')
            code = 'data_not_found';
        end
        write_result(res_path, false, code, ME.message, '', struct());
    end
end

% ------------------------------------------------------------
% 内部函数：把结果写成 result.json，供 Python 端 read_result 读取
%   字段：ok / error / message / image_path / meta
% ------------------------------------------------------------
function write_result(res_path, ok, err_code, message, image_path, meta)
    r = struct();
    r.ok = logical(ok);
    r.error = char(string(err_code));
    r.message = char(string(message));
    r.image_path = char(string(image_path));
    if nargin < 6 || isempty(meta)
        r.meta = struct();
    else
        r.meta = meta;
    end

    txt = jsonencode(r);
    fid = fopen(res_path, 'w');
    if fid < 0
        error('draw_dispatch:WriteFailed', 'cannot write result.json');
    end
    cleaner = onCleanup(@() fclose(fid));
    fprintf(fid, '%s', txt);
end

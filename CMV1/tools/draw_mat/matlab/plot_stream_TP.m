function meta = plot_stream_TP(tbl, req, fig_path)
%PLOT_STREAM_TP  流股温度-压力双柱状图（stream_tp）
%   data.csv 列: stream, T, P
%   左轴画温度（蓝），右轴画压力（橙），双轴便于量纲不同的两列对比。
%
%   参数:
%       tbl       readtable 读出的 data.csv
%       req       绘图请求（title / ylabel_left / ylabel_right 等）
%       fig_path  输出图片路径
%   返回:
%       meta      统计信息结构体（流股数、T/P 极值），写入 result.json

    % ---- 数据校验：缺列 / 非数值直接报错 ----
    must_have_columns(tbl, {'stream', 'T', 'P'});

    streams = tick_labels(tbl.stream);
    T = double(tbl.T);
    P = double(tbl.P);
    n = numel(streams);
    x = 1:n;

    if any(~isfinite(T)) || any(~isfinite(P))
        error('spec_invalid: T/P contain non-finite values');
    end

    % ---- 建图：隐藏画布，宽度随流股数量自适应 ----
    fig = new_hidden_figure(max(900, 120 * n), 440);
    ax = axes(fig);
    hold(ax, 'on');

    % 左轴：温度柱（蓝）
    yyaxis(ax, 'left');
    b1 = bar(ax, x - 0.18, T, 0.32);
    b1.FaceColor = [0.20 0.45 0.75];
    b1.EdgeColor = 'none';
    ylabel(ax, get_req(req, 'ylabel_left', 'Temperature'));
    draw_style(ax);

    % 右轴：压力柱（橙），左右柱并排不重叠
    yyaxis(ax, 'right');
    b2 = bar(ax, x + 0.18, P, 0.32);
    b2.FaceColor = [0.85 0.42 0.18];
    b2.EdgeColor = 'none';
    ylabel(ax, get_req(req, 'ylabel_right', 'Pressure'));
    draw_style(ax);

    % X 轴：流股名，斜排防重叠
    set(ax, 'XTick', x, 'XTickLabel', streams);
    xtickangle(ax, 30);
    apply_figure_title(req);
    legend(ax, {'T', 'P'}, 'Location', 'best', 'FontSize', 10);
    hold(ax, 'off');

    % ---- 导出并关闭隐藏图 ----
    export_figure(fig, fig_path, req);
    close(fig);

    % ---- 统计信息回传给 Python ----
    meta = struct();
    meta.n_streams = n;
    meta.T_min = min(T);
    meta.T_max = max(T);
    meta.P_min = min(P);
    meta.P_max = max(P);
end

function meta = plot_component_track(tbl, req, fig_path)
%PLOT_COMPONENT_TRACK  组分沿流股分布图（component_track）
%   data.csv 列: stream, value
%   画某组分在各流股的值（摩尔分率 / 摩尔流 / 质量流），
%   并标出最大值位置。
%
%   参数:
%       tbl       readtable 读出的 data.csv
%       req       绘图请求（title / ylabel 等）
%       fig_path  输出图片路径
%   返回:
%       meta      统计信息（流股数、最大值及所在流股、合计）

    % ---- 数据校验 ----
    must_have_columns(tbl, {'stream', 'value'});

    streams = tick_labels(tbl.stream);
    y = double(tbl.value);
    n = numel(streams);
    x = 1:n;

    if any(~isfinite(y))
        error('spec_invalid: value contains non-finite values');
    end

    % ---- 建图：紫色柱，宽度随流股数量自适应 ----
    fig = new_hidden_figure(max(900, 110 * n), 440);
    ax = axes(fig);
    b = bar(ax, x, y, 0.55);
    b.FaceColor = [0.52 0.32 0.68];
    b.EdgeColor = 'none';

    set(ax, 'XTick', x, 'XTickLabel', streams);
    xtickangle(ax, 30);
    ylabel(ax, get_req(req, 'ylabel', 'Component value'));
    draw_style(ax);
    apply_figure_title(req);

    % ---- 标注最大值：红点 + "max=..." 文本 ----
    [ymax, idx] = max(y);
    hold(ax, 'on');
    plot(ax, idx, ymax, 'o', ...
        'MarkerSize', 9, ...
        'MarkerFaceColor', [0.85 0.2 0.2], ...
        'MarkerEdgeColor', [0.5 0.05 0.05], ...
        'LineWidth', 1.2);
    text(ax, idx, ymax, sprintf('  max=%.4g', ymax), ...
        'VerticalAlignment', 'bottom', ...
        'FontSize', 10, ...
        'Color', [0.45 0.05 0.05], ...
        'FontWeight', 'bold');
    hold(ax, 'off');

    % ---- 导出并关闭 ----
    export_figure(fig, fig_path, req);
    close(fig);

    % ---- 统计信息回传给 Python ----
    meta = struct();
    meta.n_streams = n;
    meta.max_value = ymax;
    meta.max_stream = streams{idx};
    meta.total_value = sum(y);
end

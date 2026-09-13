function meta = plot_stream_composition(tbl, req, fig_path)
%PLOT_STREAM_COMPOSITION  物流组成柱状图（stream_composition）
%   data.csv 列: component, fraction
%   按摩尔分率从高到低排序画柱，柱顶标注数值。
%
%   参数:
%       tbl       readtable 读出的 data.csv
%       req       绘图请求（title / ylabel 等）
%       fig_path  输出图片路径
%   返回:
%       meta      统计信息（组分个数、分率合计、最大组分）

    % ---- 数据校验：缺列 / 非数值 / 负分率直接报错 ----
    must_have_columns(tbl, {'component', 'fraction'});

    frac = double(tbl.fraction);
    if any(~isfinite(frac))
        error('spec_invalid: fraction contains non-finite values');
    end
    if any(frac < -1e-9)
        error('spec_invalid: fraction has negative values');
    end

    % ---- 从高到低排序，标签跟着数据一起排 ----
    [frac, order] = sort(frac, 'descend');
    comps = tick_labels(tbl.component);
    comps = comps(order);
    n = numel(comps);
    x = 1:n;

    % ---- 建图：绿色柱，宽度随组分数量自适应 ----
    fig = new_hidden_figure(max(720, 90 * n), 440);
    ax = axes(fig);
    b = bar(ax, x, frac, 0.62);
    b.FaceColor = [0.22 0.55 0.42];
    b.EdgeColor = 'none';

    set(ax, 'XTick', x, 'XTickLabel', comps);
    xtickangle(ax, 30);
    ylabel(ax, get_req(req, 'ylabel', 'Fraction'));
    % Y 轴上限：至少到 1，分率大于 1 时留 15% 余量
    y_top = max(1.0, max(frac) * 1.15);
    if y_top == 0
        y_top = 1;
    end
    ylim(ax, [0 y_top]);
    draw_style(ax);
    apply_figure_title(req);

    % 柱顶标注数值（0 值不标，避免柱顶堆满"0"）
    for i = 1:n
        if frac(i) > 0
            text(ax, x(i), frac(i), sprintf('%.3g', frac(i)), ...
                'HorizontalAlignment', 'center', ...
                'VerticalAlignment', 'bottom', ...
                'FontSize', 9, 'Color', [0.2 0.2 0.2]);
        end
    end

    % ---- 导出并关闭 ----
    export_figure(fig, fig_path, req);
    close(fig);

    % ---- 统计信息回传给 Python ----
    meta = struct();
    meta.n_components = n;
    meta.fraction_sum = sum(frac);
    meta.top_component = comps{1};
    meta.top_fraction = frac(1);
end

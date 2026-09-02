function meta = plot_balance_check(tbl, req, fig_path)
%PLOT_BALANCE_CHECK  设备进出衡算图（balance_check）
%   data.csv 列: side, name, value   （side = in | out）
%   左子图：逐条列出进/出流股（蓝=进，橙=出）；
%   右子图：进出合计对比 + 残差（Delta）与相对误差。
%
%   参数:
%       tbl       readtable 读出的 data.csv
%       req       绘图请求（title / ylabel 等）
%       fig_path  输出图片路径
%   返回:
%       meta      衡算统计（进/出合计、残差、相对误差）

    % ---- 数据校验：缺列 / 非数值 / side 取值 ----
    must_have_columns(tbl, {'side', 'name', 'value'});

    side = lower(strtrim(string(tbl.side)));
    names = tick_labels(tbl.name);
    vals = double(tbl.value);

    if any(~isfinite(vals))
        error('spec_invalid: value contains non-finite values');
    end
    if ~all(side == "in" | side == "out")
        error('spec_invalid: side must be "in" or "out"');
    end

    % 进出合计与残差（相对误差按 in 合计归一）
    in_mask  = side == "in";
    out_mask = side == "out";
    if ~any(in_mask) || ~any(out_mask)
        error('data_not_found: need at least one in and one out row');
    end

    in_sum  = sum(vals(in_mask));
    out_sum = sum(vals(out_mask));
    residual = out_sum - in_sum;
    if abs(in_sum) > eps
        rel_err = residual / in_sum;
    else
        rel_err = NaN;   % 进料合计为 0 时相对误差无意义
    end

    % ---- 建图：1x2 双子图，宽度随流股数量自适应 ----
    n = numel(vals);
    fig = new_hidden_figure(max(860, 70 * n + 280), 440);

    % 左子图：逐流股柱状图，进=蓝 出=橙
    ax1 = subplot(1, 2, 1);
    b = bar(ax1, 1:n, vals, 0.62);
    b.FaceColor = 'flat';
    cdata = zeros(n, 3);
    cdata(in_mask, :)  = repmat([0.30 0.58 0.88], sum(in_mask), 1);
    cdata(out_mask, :) = repmat([0.90 0.45 0.25], sum(out_mask), 1);
    b.CData = cdata;
    b.EdgeColor = 'none';
    set(ax1, 'XTick', 1:n, 'XTickLabel', names);
    xtickangle(ax1, 30);
    ylabel(ax1, get_req(req, 'ylabel', 'Flow'));
    title(ax1, 'Streams');
    draw_style(ax1);

    % 右子图：进出合计对比柱
    ax2 = subplot(1, 2, 2);
    bb = bar(ax2, [1 2], [in_sum, out_sum], 0.5);
    bb.FaceColor = 'flat';
    bb.CData = [0.30 0.58 0.88; 0.90 0.45 0.25];
    bb.EdgeColor = 'none';
    set(ax2, 'XTick', [1 2], 'XTickLabel', {'IN total', 'OUT total'});
    ylabel(ax2, get_req(req, 'ylabel', 'Flow'));
    % 标题直接写残差与相对误差，一眼看出闭合情况
    if isfinite(rel_err)
        title(ax2, sprintf('Balance  \Delta=%.4g  (%.2f%%)', residual, 100 * rel_err));
    else
        title(ax2, sprintf('Balance  \Delta=%.4g', residual));
    end
    draw_style(ax2);

    apply_sgtitle(req);

    % ---- 导出并关闭 ----
    export_figure(fig, fig_path, req);
    close(fig);

    % ---- 衡算统计回传给 Python ----
    meta = struct();
    meta.n_in = sum(in_mask);
    meta.n_out = sum(out_mask);
    meta.in_sum = in_sum;
    meta.out_sum = out_sum;
    meta.residual = residual;
    meta.rel_error = rel_err;
end

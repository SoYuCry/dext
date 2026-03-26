#!/usr/bin/env python3
"""Remove dead methods from exchanges/base/exchange.py"""

import re
import sys
import os
import ast

EXCHANGE_PY = os.path.join(os.path.dirname(__file__), '..', 'exchanges', 'base', 'exchange.py')
EXCHANGE_PY = os.path.abspath(EXCHANGE_PY)

# Complete list of methods to remove
METHODS_TO_REMOVE = {
    # Category A: watch_*/un_watch_* WebSocket stubs
    'watch_liquidations', 'watch_liquidations_for_symbols', 'watch_my_liquidations',
    'watch_my_liquidations_for_symbols', 'watch_trades', 'un_watch_orders', 'un_watch_trades',
    'watch_trades_for_symbols', 'un_watch_trades_for_symbols', 'watch_my_trades_for_symbols',
    'watch_orders_for_symbols', 'watch_ohlcv_for_symbols', 'un_watch_ohlcv_for_symbols',
    'watch_order_book_for_symbols', 'un_watch_order_book_for_symbols', 'un_watch_positions',
    'un_watch_ticker', 'un_watch_mark_price', 'un_watch_mark_prices', 'watch_order_book',
    'un_watch_order_book', 'watch_funding_rate', 'watch_funding_rates',
    'watch_funding_rates_for_symbols', 'watch_ohlcv', 'watch_position', 'watch_positions',
    'watch_position_for_symbols', 'watch_balance', 'watch_ticker', 'watch_bids_asks',
    'watch_tickers', 'un_watch_tickers', 'watch_orders', 'watch_my_trades', 'un_watch_ohlcv',
    'watch_mark_price', 'watch_mark_prices', 'un_watch_my_trades', 'un_watch_bids_asks',

    # Category B: Margin/leverage/borrowing
    'add_margin', 'reduce_margin', 'set_margin', 'set_margin_mode', 'set_leverage',
    'fetch_leverage', 'fetch_leverages', 'borrow_margin', 'repay_margin',
    'borrow_cross_margin', 'repay_cross_margin', 'fetch_borrow_rate', 'transfer',
    'fetch_transfers', 'fetch_cross_borrow_rate', 'fetch_cross_borrow_rates',
    'fetch_isolated_borrow_rate', 'fetch_isolated_borrow_rates', 'set_position_mode',
    'close_position', 'close_all_positions',

    # Category C: Deposit/withdrawal
    'fetch_deposits', 'fetch_withdrawals', 'fetch_deposit_address', 'fetch_deposit_addresses',
    'create_deposit_address', 'withdraw', 'fetch_transactions', 'fetch_deposits_withdrawals',
    'fetch_transaction_fee', 'fetch_transaction_fees', 'fetch_deposit_withdraw_fee',
    'fetch_deposit_withdraw_fees', 'fetch_deposit_addresses_by_network',

    # Category D: Order wrappers + _ws stubs
    'create_limit_order', 'create_market_order', 'create_limit_buy_order',
    'create_limit_sell_order', 'create_market_buy_order', 'create_market_sell_order',
    'create_stop_order', 'create_stop_limit_order', 'create_stop_market_order',
    'create_trailing_amount_order', 'create_trailing_percent_order', 'edit_order',
    'edit_limit_order', 'edit_limit_buy_order', 'edit_limit_sell_order',
    'cancel_all_orders', 'cancel_all_orders_after', 'cancel_unified_order',
    'create_order_with_take_profit_and_stop_loss', 'create_orders',
    'set_take_profit_and_stop_loss_params', 'create_trigger_order',
    'create_stop_loss_order', 'create_take_profit_order', 'create_post_only_order',
    'create_reduce_only_order', 'create_market_order_with_cost',
    'create_market_buy_order_with_cost', 'create_market_sell_order_with_cost',
    'fetch_trades_ws', 'fetch_order_book_ws', 'fetch_ohlcv_ws', 'edit_order_ws',
    'fetch_position_ws', 'fetch_positions_for_symbol_ws', 'fetch_positions_ws',
    'fetch_balance_ws', 'fetch_ticker_ws', 'fetch_tickers_ws', 'fetch_order_ws',
    'create_trailing_amount_order_ws', 'create_trailing_percent_order_ws',
    'create_market_order_with_cost_ws', 'create_trigger_order_ws',
    'create_stop_loss_order_ws', 'create_take_profit_order_ws',
    'create_order_with_take_profit_and_stop_loss_ws', 'create_order_ws',
    'cancel_order_ws', 'cancel_orders_ws', 'cancel_all_orders_ws', 'fetch_orders_ws',
    'fetch_open_orders_ws', 'fetch_closed_orders_ws', 'fetch_my_trades_ws',
    'fetch_deposits_ws', 'fetch_withdrawals_ws', 'create_limit_order_ws',
    'create_market_order_ws', 'create_limit_buy_order_ws', 'create_limit_sell_order_ws',
    'create_market_buy_order_ws', 'create_market_sell_order_ws',
    'create_post_only_order_ws', 'create_reduce_only_order_ws', 'create_stop_order_ws',
    'create_stop_limit_order_ws', 'create_stop_market_order_ws', 'fetch_trading_fees_ws',
    'withdraw_ws', 'create_orders_ws', 'fetch_orders_by_status_ws',

    # Category E: Unused crypto signing
    'ecdsa', '_ecdsa_secp256k1_coincurve', 'axolotl', 'rsa', 'jwt',
    'eth_abi_encode', 'eth_encode_structured_data', 'eth_get_address_from_private_key',
    'retrieve_stark_account', 'starknet_encode_structured_data', 'starknet_sign',
    'privateKeyToAddress', 'crc32', 'retrieve_dydx_credentials', 'load_dydx_protos',
    'to_dydx_long', 'encode_dydx_tx_for_simulation', 'encode_dydx_tx_for_signing',
    'encode_dydx_tx_raw', 'get_zk_contract_signature_obj', 'get_zk_transfer_signature_obj',

    # Category F: Funding rates
    'fetch_funding_rate', 'fetch_funding_rates', 'fetch_funding_rate_history',
    'fetch_funding_history', 'fetch_funding_intervals',

    # Category G: Options/convert/legacy
    'fetch_greeks', 'fetch_all_greeks', 'fetch_option_chain', 'fetch_option',
    'fetch_convert_quote', 'create_convert_trade', 'fetch_convert_trade',
    'fetch_convert_trade_history', 'fetch_convert_currencies',
    'convert_type_to_account', 'fetch_payment_methods', 'convert_expire_date',
    'convert_expire_date_to_market_id_date', 'convert_market_id_expire_date',
    'convert_trading_view_to_ohlcv', 'convert_ohlcv_to_trading_view',

    # Category H: Additional dead stubs
    'fetch_accounts', 'fetch_margin_modes', 'fetch_margin_mode', 'fetch_time',
    'fetch_trading_limits', 'fetch_leverage_tiers', 'fetch_long_short_ratio',
    'fetch_long_short_ratio_history', 'fetch_margin_adjustment_history',
    'fetch_open_interest_history', 'fetch_open_interest', 'fetch_open_interests',
    'sign_in', 'fetch_positions_risk', 'fetch_bids_asks', 'fetch_borrow_interest',
    'fetch_ledger', 'fetch_ledger_entry', 'fetch_partial_balance', 'fetch_free_balance',
    'fetch_used_balance', 'fetch_total_balance', 'fetch_status', 'fetch_mark_prices',
    'fetch_order_books', 'fetch_order_status', 'fetch_unified_order',
    'fetch_position_mode', 'fetch_order_trades', 'fetch_canceled_orders',
    'fetch_canceled_and_closed_orders', 'fetch_my_liquidations', 'fetch_liquidations',
    'fetch_l3_order_book', 'fetch_last_prices', 'fetch_trading_fees', 'fetch_trading_fee',
    'fetch_fees', 'check_required_dependencies', 'enable_demo_trading', 'is_post_only',

    # Category I: Dead large utility methods
    'fetch_paginated_call_dynamic', 'fetch_paginated_call_cursor',
    'fetch_paginated_call_deterministic', 'fetch_paginated_call_incremental',
    'build_ohlcvc', 'fetch_web_endpoint', 'safe_ledger_entry', 'parse_leverage_tiers',
    'parse_conversions', 'parse_last_prices', 'clean_cache',

    # Category J: Dead parse stubs
    'parse_transfer', 'parse_account', 'parse_ledger_entry',
    'parse_market_leverage_tiers', 'parse_funding_rate_history', 'parse_borrow_interest',
    'parse_isolated_borrow_rate', 'parse_ws_trade', 'parse_ws_order',
    'parse_ws_order_trade', 'parse_ws_ohlcv',
}


def find_method_ranges(lines):
    """Find all class-level method ranges using `    def ` pattern.

    Returns list of (start, end, name) tuples (0-indexed, inclusive).
    start includes decorators, end is the last line of the method body.

    Strategy: find all `    def ` lines, then each method's body extends
    until the next `    def ` line (or its decorator), or end of class.
    We do NOT use indentation of body lines to determine boundaries,
    because docstrings can contain lines with arbitrary indentation.
    """
    n = len(lines)

    # Step 1: Find all 4-space indent `def` lines
    def_lines = []  # (line_index, method_name)
    for i, line in enumerate(lines):
        m = re.match(r'^    def (\w+)\s*\(', line)
        if m:
            def_lines.append((i, m.group(1)))

    if not def_lines:
        return []

    # Step 2: For each def, find decorator start (looking backwards)
    method_starts = []  # (decorator_start, def_line, method_name)
    for def_idx, name in def_lines:
        start = def_idx
        j = def_idx - 1
        while j >= 0:
            stripped = lines[j].rstrip()
            if stripped == '':
                j -= 1
                continue
            if re.match(r'^    @', lines[j]):
                start = j
                j -= 1
            else:
                break
        method_starts.append((start, def_idx, name))

    # Step 3: Determine end of each method
    # A method ends just before the start of the next method (its decorator_start),
    # or at the end of the class/file.
    # We also need to handle the class ending (line with indent 0 like `class` or module-level code).
    method_ranges = []
    for idx, (dec_start, def_line, name) in enumerate(method_starts):
        if idx + 1 < len(method_starts):
            # End is just before the next method's decorator/blank-line zone
            next_start = method_starts[idx + 1][0]
            end = next_start - 1
        else:
            # Last method: extends to end of file (or end of class)
            end = n - 1

        # Trim trailing blank lines
        while end > def_line and lines[end].strip() == '':
            end -= 1

        method_ranges.append((dec_start, end, name))

    return method_ranges


def parse_and_remove(source_lines, methods_to_remove):
    """Remove specified methods from the source."""
    lines = source_lines
    method_ranges = find_method_ranges(lines)

    # Build set of line indices to remove
    lines_to_remove = set()
    removed_methods = []
    for start, end, name in method_ranges:
        if name in methods_to_remove:
            # Also remove blank lines immediately before the method (up to 1)
            actual_start = start
            if actual_start > 0 and lines[actual_start - 1].strip() == '':
                actual_start -= 1

            for li in range(actual_start, end + 1):
                lines_to_remove.add(li)
            removed_methods.append(name)

    # Build output
    output_lines = []
    for i, line in enumerate(lines):
        if i not in lines_to_remove:
            output_lines.append(line)

    # Clean up excessive blank lines (more than 2 consecutive)
    cleaned = []
    blank_count = 0
    for line in output_lines:
        if line.strip() == '':
            blank_count += 1
            if blank_count <= 2:
                cleaned.append(line)
        else:
            blank_count = 0
            cleaned.append(line)

    return cleaned, removed_methods


def main():
    with open(EXCHANGE_PY, 'r') as f:
        lines = f.readlines()

    original_count = len(lines)
    print(f"Original: {original_count} lines")
    print(f"Methods to remove: {len(METHODS_TO_REMOVE)}")

    cleaned, removed = parse_and_remove(lines, METHODS_TO_REMOVE)

    final_count = len(cleaned)
    print(f"Final: {final_count} lines")
    print(f"Removed: {original_count - final_count} lines")
    print(f"Methods removed: {len(removed)}")

    # Check which methods were NOT found
    removed_set = set(removed)
    not_found = METHODS_TO_REMOVE - removed_set
    if not_found:
        print(f"\nWARNING: {len(not_found)} methods not found in file:")
        for m in sorted(not_found):
            print(f"  - {m}")

    # Write output
    with open(EXCHANGE_PY, 'w') as f:
        f.writelines(cleaned)

    print(f"\nWrote {final_count} lines to {EXCHANGE_PY}")


if __name__ == '__main__':
    main()

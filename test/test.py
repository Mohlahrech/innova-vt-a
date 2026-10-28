# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles
from cocotb.utils import get_sim_time

CLK_NS = 10  # 100 MHz

# Cycles per UART bit: prescale * 8, with prescale = 100 MHz / (115200 * 8) = 108.
BIT_CYCLES = 108 * 8

# PWM period is the same 5.12 us it was at 50 MHz: 256 steps, one step every 2 clocks.
PWM_PERIOD_NS = 5120


async def send_byte(dut, value):
    """Drive one 8N1 UART frame on ui_in[3] (RX)."""
    bits = [0] + [(value >> i) & 1 for i in range(8)] + [1]
    for b in bits:
        dut.ui_in.value = b << 3
        await ClockCycles(dut.clk, BIT_CYCLES)


async def uart_monitor(dut, received):
    """Decode 8N1 frames on uio_out[0] (TX) into `received`."""
    while True:
        await ClockCycles(dut.clk, 1)
        if int(dut.uio_out.value) & 1:
            continue
        await ClockCycles(dut.clk, BIT_CYCLES // 2)
        if int(dut.uio_out.value) & 1:
            continue  # glitch, not a start bit
        value = 0
        for i in range(8):
            await ClockCycles(dut.clk, BIT_CYCLES)
            value |= (int(dut.uio_out.value) & 1) << i
        await ClockCycles(dut.clk, BIT_CYCLES)
        assert int(dut.uio_out.value) & 1, "TX stop bit must be high"
        received.append(value)


async def period_ns(dut, bit):
    """Time between two rising edges of a uo_out bit."""
    edges = []
    prev = (int(dut.uo_out.value) >> bit) & 1
    while len(edges) < 2:
        await ClockCycles(dut.clk, 1)
        cur = (int(dut.uo_out.value) >> bit) & 1
        if cur and not prev:
            edges.append(get_sim_time(unit="ns"))
        prev = cur
    return edges[1] - edges[0]


async def duty_of(dut, bit, cycles=512):
    """Fraction of cycles a uo_out bit is high."""
    high = 0
    for _ in range(cycles):
        await ClockCycles(dut.clk, 1)
        high += (int(dut.uo_out.value) >> bit) & 1
    return high / cycles


@cocotb.test()
async def test_project(dut):
    dut._log.info("Start")

    clock = Clock(dut.clk, CLK_NS, unit="ns")
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 1 << 3  # RX idles high
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, BIT_CYCLES)

    assert await duty_of(dut, 0) == 0, "channel 0 must be off after reset"

    echoed = []
    cocotb.start_soon(uart_monitor(dut, echoed))

    # Channel 0 to full scale, channel 2 to about half.
    await send_byte(dut, 0x80)
    await send_byte(dut, 0x7F)
    await send_byte(dut, 0x82)
    await send_byte(dut, 0x40)
    await ClockCycles(dut.clk, BIT_CYCLES * 2)

    full = await duty_of(dut, 0)
    half = await duty_of(dut, 2)
    off = await duty_of(dut, 1)
    dut._log.info(f"duty ch0={full:.3f} ch2={half:.3f} ch1={off:.3f}")
    assert full > 0.95
    assert 0.45 < half < 0.55
    assert off == 0

    period = await period_ns(dut, 2)
    dut._log.info(f"PWM period {period} ns")
    assert period == PWM_PERIOD_NS

    await ClockCycles(dut.clk, BIT_CYCLES * 10)  # let the last echo finish
    assert echoed == [0x80, 0x7F, 0x82, 0x40], f"echo mismatch: {echoed}"

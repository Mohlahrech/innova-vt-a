<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

A UART receiver (115200 baud, 8N1, on `ui[3]`) feeds a small command decoder that sets the duty cycle of
15 PWM channels. Every received byte is echoed back on TX (`uio[0]`).

- A byte with bit 7 set selects a channel: bits 3:0 give the channel number, 0 to 14 (15 is ignored).
- The next byte, with bit 7 clear, sets that channel's duty: 0 to 127, stretched to 0 to 255.

All channels share one 8-bit counter, so the PWM period is 256 steps. The design runs at 100 MHz with
the counter stepping every other clock, giving a PWM frequency of 195.3 kHz (5.12 us period).

## How to test

Hold `rst_n` low, then release it. Connect a 115200-baud 3.3 V UART: its TX to `ui[3]`, its RX to
`uio[0]`. Send `0x80 0x7F` to drive channel 0 (`uo[0]`) to full scale, or `0x82 0x40` for channel 2 at
about half. Each byte you send should come back on the UART.

## External hardware

LEDs (with series resistors) on the PWM outputs, and a USB-to-UART adapter.

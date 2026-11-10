# Market data

Market data come from Yahoo Finance (daily OHLC, volume and adjusted close, USD). The analysis uses 95 instructor-selected equities and SPY. The download script reads the fixed ticker list and dates from the study configuration, records one response and checksum per ticker, and creates a date/ticker CSV. The frozen run spans January 3, 2022 through November 9, 2026; November 10 is not used because an Adobe bar from that date had an inconsistent open and high. Raw data and Canvas course attachments are kept locally rather than included in the public repository.

return {
  {
    "bjarneo/aether.nvim",
    branch = "v3",
    name = "aether",
    priority = 1000,
    opts = {
      colors = {
        bg = "#0A0118",
        dark_bg = "#080111",
        darker_bg = "#05010C",
        lighter_bg = "#18152F",

        fg = "#F8F8F2",
        dark_fg = "#948DAE",
        light_fg = "#D9D3EB",
        bright_fg = "#FFFFFF",
        muted = "#57517A",

        red = "#FF4D6D",
        yellow = "#FFEB66",
        orange = "#FFAD66",
        green = "#33FF44",
        cyan = "#8BE9FD",
        blue = "#829BFF",
        magenta = "#DF13A2",
        brown = "#A8654D",

        bright_red = "#FF708C",
        bright_yellow = "#FFFFA5",
        bright_green = "#33FF44",
        bright_cyan = "#A4FFFF",
        bright_blue = "#ADBDFF",
        bright_magenta = "#FF92DF",

        accent = "#33FF44",
        cursor = "#FFFFFF",
        foreground = "#F8F8F2",
        background = "#0A0118",
        selection = "#5B4B8A",
        selection_foreground = "#FFFFFF",
        selection_background = "#5B4B8A",
      },
    },
  },
  {
    "LazyVim/LazyVim",
    opts = {
      colorscheme = "aether",
    },
  },
}

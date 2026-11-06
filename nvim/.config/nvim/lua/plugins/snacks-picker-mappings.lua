return {
  "folke/snacks.nvim",
  opts = {
    picker = {
      win = {
        input = {
          keys = {
            ["s"] = { "edit_vsplit", mode = { "n" } },
            ["S"] = { "edit_split", mode = { "n" } },
            ["<c-v>"] = false,
            ["<c-s>"] = false,
          },
        },
        list = {
          keys = {
            ["s"] = "edit_vsplit",
            ["S"] = "edit_split",
            ["<c-v>"] = false,
            ["<c-s>"] = false,
          },
        },
      },
    },
  },
}

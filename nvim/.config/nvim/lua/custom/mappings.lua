local M = {}

M.crates = {
  n = {
    ["<leader>rcu"] = {
      function ()
        require("crates").upgrade_all_crates()
      end,
      "Update crates"
    }
  }
}

M.dap = {
  plugin = true,
  n = {
    ["<leader>db"] = {
      "<cmd> DapToggleBreakpoint <CR>",
      "Add breakpoint at line"
    },
    ["<leader>dr"] = {
      "<cmd> DapContinue <CR>",
      "Run or continue the debugger"
    },
  },
}

M.dap_python = {
  plugin = true,
  n = {
    ["<leader>dpr"] = {
      function ()
        require("dap-python").test_method()
      end,
      "<cmd> DapContinue <CR>",
      "Run or continue the debugger"
    },
  }
}

M.harpoon = {
  plugin = true,
  n = {
    ["<leader>a"] = {
      function ()
        require("harpoon"):list():append()
      end,
      "Add mark"
    },
    ["<C-e>"] = {
      function ()
        require("harpoon").ui:toggle_quick_menu(require("harpoon"):list())
      end,
      "Show all marks"
    },
    ["<C-t>"] = {
      function ()
        require("harpoon"):list():select(1)
      end,
      "Go to mark 1"
    },
    ["<C-n>"] = {
      function ()
        require("harpoon"):list():select(2)
      end,
      "Go to mark 3"
    },
    ["<C-s>"] = {
      function ()
        require("harpoon"):list():select(3)
      end,
      "Go to mark 3"
    }
  }
}

M.utils = {
  n = {
    ["<leader>fd"] = {
      function ()
        vim.lsp.buf.format()
      end,
      "Format document"
    }
  }
}

return M

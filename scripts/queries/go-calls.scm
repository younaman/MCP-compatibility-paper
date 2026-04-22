;; ========================
;; Go 函数 & 方法调用
;; ========================

;; 方法调用：recv.method()
(call_expression
  function: (selector_expression
    operand: (_) @recv
    field: (field_identifier) @method)) @mcall

;; 普通函数调用：foo()
(call_expression
  function: (identifier) @func) @fcall




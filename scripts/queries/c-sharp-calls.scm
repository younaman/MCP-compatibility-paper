;; ========================
;; C# 函数 & 方法调用
;; ========================

;; 方法调用：obj.Method()
(invocation_expression
  function: (member_access_expression
    expression: (_) @recv
    name: (_) @method)) @mcall

;; 普通函数调用：Func()
(invocation_expression
  function: (identifier) @func) @fcall

;; 构造函数调用：new Class()
(object_creation_expression
  type: (_) @func) @fcall




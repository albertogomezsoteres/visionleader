;; Indoor navigation domain — shared by ALL 14 UFV buildings (G, CD, H, P, O, M, N, CSQ, K, CSC, C, E, CM, LCB).
;; Building G uses measured metric distances; all others default to 15 m/hop.
;; Elevator and stairs presence is controlled by the problem file, not the domain.
;;
;; Cost model (units = seconds of effort):
;;   caminar: (distancia u1 u2) ≈15m  verificar_ascensor: 5
;;   usar_ascensor: 15                 validar_escaleras: 10
;;   subir_escaleras: 30               bajar_escaleras: 25
;;   subir_escaleras_rapido: 12        bajar_escaleras_rapido: 8
;;
;; Elevator presence is controlled by the problem file: buildings without
;; an elevator simply declare no (es_ascensor) or (conectado_ascensor) facts.

(define (domain building-indoor)
  (:requirements :strips :typing :action-costs)

  (:types robot ubicacion planta - object)

  (:functions
    (total-cost) - number
    (distancia ?u1 - ubicacion ?u2 - ubicacion) - number
  )

  (:predicates
    (en ?r - robot ?u - ubicacion)
    (en_planta ?u - ubicacion ?p - planta)

    (conectado_pasillo        ?u1 ?u2 - ubicacion)
    (conectado_ascensor       ?u1 ?u2 - ubicacion)
    (conectado_escalera_subir ?u1 ?u2 - ubicacion)
    (conectado_escalera_bajar ?u1 ?u2 - ubicacion)

    (es_ascensor ?u - ubicacion)
    (es_escalera ?u - ubicacion)

    (ascensor_disponible   ?u - ubicacion)
    (escaleras_verificadas ?u - ubicacion)

    (abierto ?u - ubicacion)

    (modo_rapido)
  )

  (:action caminar
    :parameters (?r - robot ?u1 - ubicacion ?u2 - ubicacion)
    :precondition (and (en ?r ?u1) (conectado_pasillo ?u1 ?u2) (abierto ?u2))
    :effect (and (not (en ?r ?u1)) (en ?r ?u2) (increase (total-cost) (distancia ?u1 ?u2)))
  )

  (:action verificar_ascensor
    :parameters (?r - robot ?u - ubicacion)
    :precondition (and (en ?r ?u) (es_ascensor ?u) (abierto ?u))
    :effect (and (ascensor_disponible ?u) (increase (total-cost) 5))
  )

  (:action usar_ascensor
    :parameters (?r - robot ?u1 - ubicacion ?u2 - ubicacion)
    :precondition (and
      (en ?r ?u1) (es_ascensor ?u1) (ascensor_disponible ?u1)
      (conectado_ascensor ?u1 ?u2))
    :effect (and
      (not (en ?r ?u1)) (en ?r ?u2)
      (not (ascensor_disponible ?u1)) (increase (total-cost) 15))
  )

  (:action validar_escaleras
    :parameters (?r - robot ?u - ubicacion)
    :precondition (and (en ?r ?u) (es_escalera ?u) (abierto ?u) (not (modo_rapido)))
    :effect (and (escaleras_verificadas ?u) (increase (total-cost) 10))
  )

  (:action subir_escaleras
    :parameters (?r - robot ?u1 - ubicacion ?u2 - ubicacion)
    :precondition (and
      (en ?r ?u1) (es_escalera ?u1) (escaleras_verificadas ?u1)
      (conectado_escalera_subir ?u1 ?u2))
    :effect (and
      (not (en ?r ?u1)) (en ?r ?u2)
      (not (escaleras_verificadas ?u1)) (increase (total-cost) 30))
  )

  (:action bajar_escaleras
    :parameters (?r - robot ?u1 - ubicacion ?u2 - ubicacion)
    :precondition (and
      (en ?r ?u1) (es_escalera ?u1) (escaleras_verificadas ?u1)
      (conectado_escalera_bajar ?u1 ?u2))
    :effect (and
      (not (en ?r ?u1)) (en ?r ?u2)
      (not (escaleras_verificadas ?u1)) (increase (total-cost) 25))
  )

  (:action subir_escaleras_rapido
    :parameters (?r - robot ?u1 - ubicacion ?u2 - ubicacion)
    :precondition (and
      (en ?r ?u1) (es_escalera ?u1) (modo_rapido)
      (conectado_escalera_subir ?u1 ?u2))
    :effect (and (not (en ?r ?u1)) (en ?r ?u2) (increase (total-cost) 12))
  )

  (:action bajar_escaleras_rapido
    :parameters (?r - robot ?u1 - ubicacion ?u2 - ubicacion)
    :precondition (and
      (en ?r ?u1) (es_escalera ?u1) (modo_rapido)
      (conectado_escalera_bajar ?u1 ?u2))
    :effect (and (not (en ?r ?u1)) (en ?r ?u2) (increase (total-cost) 8))
  )
)

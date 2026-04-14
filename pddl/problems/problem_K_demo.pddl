(define (problem k-demo)
  (:domain building-indoor)

  (:objects
    robot1 - robot
    aula_k_1 aula_k_2 entrada_k escaleras_p0 escaleras_p1 escaleras_p2 - ubicacion
    planta_0 planta_1 planta_2 - planta
  )

  (:init
    (= (total-cost) 0)
    (en robot1 entrada_k)
    (abierto aula_k_1)
    (abierto aula_k_2)
    (abierto entrada_k)
    (abierto escaleras_p0)
    (abierto escaleras_p1)
    (abierto escaleras_p2)
    (en_planta aula_k_1 planta_1)
    (en_planta aula_k_2 planta_2)
    (en_planta entrada_k planta_0)
    (en_planta escaleras_p0 planta_0)
    (en_planta escaleras_p1 planta_1)
    (en_planta escaleras_p2 planta_2)
    (es_escalera escaleras_p0)
    (es_escalera escaleras_p1)
    (es_escalera escaleras_p2)
    (conectado_pasillo entrada_k escaleras_p0)
    (= (distancia entrada_k escaleras_p0) 15)
    (conectado_pasillo escaleras_p0 entrada_k)
    (= (distancia escaleras_p0 entrada_k) 15)
    (conectado_pasillo aula_k_1 escaleras_p1)
    (= (distancia aula_k_1 escaleras_p1) 15)
    (conectado_pasillo escaleras_p1 aula_k_1)
    (= (distancia escaleras_p1 aula_k_1) 15)
    (conectado_pasillo aula_k_2 escaleras_p2)
    (= (distancia aula_k_2 escaleras_p2) 15)
    (conectado_pasillo escaleras_p2 aula_k_2)
    (= (distancia escaleras_p2 aula_k_2) 15)
    (conectado_escalera_subir escaleras_p0 escaleras_p1)
    (conectado_escalera_bajar escaleras_p1 escaleras_p0)
    (conectado_escalera_subir escaleras_p1 escaleras_p2)
    (conectado_escalera_bajar escaleras_p2 escaleras_p1)
  )

  (:goal
    (en robot1 aula_k_2)
  )

  (:metric minimize (total-cost))
)

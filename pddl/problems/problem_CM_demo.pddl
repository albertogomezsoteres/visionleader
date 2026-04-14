(define (problem cm-demo)
  (:domain building-indoor)

  (:objects
    robot1 - robot
    entrada_cm - ubicacion
    planta_0 - planta
  )

  (:init
    (= (total-cost) 0)
    (en robot1 entrada_cm)
    (abierto entrada_cm)
    (en_planta entrada_cm planta_0)
  )

  (:goal
    (en robot1 entrada_cm)
  )

  (:metric minimize (total-cost))
)
